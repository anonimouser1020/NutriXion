import csv
import glob
import os
import re
import json

try:
    from deep_translator import MyMemoryTranslator
except ImportError:
    MyMemoryTranslator = None

# En PC carga PyTorch y CLIP; en Android (.apk) funciona en modo ligero sin fallar
try:
    import torch
    from PIL import Image
    from transformers import CLIPProcessor, CLIPModel
    IA_PESADA_DISPONIBLE = True
except ImportError:
    IA_PESADA_DISPONIBLE = False


class AnalizadorNutricional:
    def __init__(self, carpeta_csv="."):
        self.carpeta_csv = carpeta_csv
        self.archivo_extra_json = os.path.join(self.carpeta_csv, "memoria_ia_extra.json")
        self.archivo_huellas_visuales = os.path.join(self.carpeta_csv, "huellas_visuales_ia.json")
        
        # 1. Cargamos los 5 CSV de Kaggle en modo SOLO LECTURA usando el módulo nativo csv
        self.df = self.cargar_multiples_csv()
        self.ultimas_predicciones_ia = []
        self.huellas_visuales = {}

        # Factores multiplicadores según el tamaño de la comida
        self.factores_porcion = {
            "Pequeña": 0.70,
            "Mediana": 1.00,
            "Grande": 1.45
        }

        # Prompts visuales para que CLIP detecte el tamaño de la porción en la foto
        self.prompts_tamano_clip = {
            "Pequeña": "a small food portion, single small piece, snack size, half empty plate, light serving",
            "Mediana": "a standard medium food portion, regular single meal serving on a normal plate",
            "Grande": "a large abundant food portion, overflowing full plate, double serving, family platter with lots of food"
        }

        # 2. Catálogo Nutricional Base (Porción Mediana Estándar) de Colombia y Suramérica
        self.catalogo_latino = {
            "salchipapa": {"Caloric Value": 680, "Fat": 42.0, "Saturated Fats": 14.5, "Sugars": 4.0, "Sodium": 980, "Protein": 18.0},
            "choripapa": {"Caloric Value": 740, "Fat": 46.0, "Saturated Fats": 16.5, "Sugars": 3.5, "Sodium": 1050, "Protein": 22.0},
            "empanada": {"Caloric Value": 320, "Fat": 18.5, "Saturated Fats": 7.5, "Sugars": 1.5, "Sodium": 420, "Protein": 8.5},
            "arepa": {"Caloric Value": 210, "Fat": 3.5, "Saturated Fats": 1.2, "Sugars": 1.0, "Sodium": 260, "Protein": 5.5},
            "arepa de huevo": {"Caloric Value": 390, "Fat": 22.0, "Saturated Fats": 7.8, "Sugars": 1.2, "Sodium": 440, "Protein": 11.0},
            "arepa rellena": {"Caloric Value": 460, "Fat": 21.0, "Saturated Fats": 9.0, "Sugars": 2.0, "Sodium": 620, "Protein": 24.0},
            "patacon": {"Caloric Value": 280, "Fat": 14.0, "Saturated Fats": 5.5, "Sugars": 3.0, "Sodium": 190, "Protein": 2.0},
            "aborrajado": {"Caloric Value": 360, "Fat": 18.0, "Saturated Fats": 8.2, "Sugars": 16.0, "Sodium": 310, "Protein": 8.5},
            "buñuelo": {"Caloric Value": 260, "Fat": 15.0, "Saturated Fats": 6.5, "Sugars": 4.0, "Sodium": 380, "Protein": 5.5},
            "pandebono": {"Caloric Value": 240, "Fat": 9.5, "Saturated Fats": 5.2, "Sugars": 3.0, "Sodium": 340, "Protein": 7.0},
            "deditos de queso": {"Caloric Value": 330, "Fat": 19.0, "Saturated Fats": 8.8, "Sugars": 2.0, "Sodium": 460, "Protein": 9.5},
            "papa rellena": {"Caloric Value": 380, "Fat": 19.5, "Saturated Fats": 7.2, "Sugars": 2.0, "Sodium": 490, "Protein": 12.0},
            "perro caliente colombiano": {"Caloric Value": 620, "Fat": 36.0, "Saturated Fats": 13.5, "Sugars": 9.0, "Sodium": 1120, "Protein": 16.0},
            "mazorcada": {"Caloric Value": 710, "Fat": 41.0, "Saturated Fats": 15.0, "Sugars": 8.0, "Sodium": 950, "Protein": 28.0},
            "bandeja paisa": {"Caloric Value": 1150, "Fat": 58.0, "Saturated Fats": 22.0, "Sugars": 12.0, "Sodium": 1350, "Protein": 54.0},
            "sancocho": {"Caloric Value": 490, "Fat": 14.0, "Saturated Fats": 4.8, "Sugars": 4.0, "Sodium": 580, "Protein": 32.0},
            "mute santandereano": {"Caloric Value": 520, "Fat": 16.5, "Saturated Fats": 6.0, "Sugars": 3.5, "Sodium": 610, "Protein": 34.0},
            "ajiaco": {"Caloric Value": 510, "Fat": 18.0, "Saturated Fats": 7.5, "Sugars": 3.0, "Sodium": 590, "Protein": 30.0},
            "lechona": {"Caloric Value": 640, "Fat": 38.0, "Saturated Fats": 14.0, "Sugars": 1.5, "Sodium": 780, "Protein": 31.0},
            "tamal": {"Caloric Value": 480, "Fat": 23.0, "Saturated Fats": 8.5, "Sugars": 2.0, "Sodium": 640, "Protein": 21.0},
            "tamal santandereano": {"Caloric Value": 510, "Fat": 24.0, "Saturated Fats": 8.8, "Sugars": 2.5, "Sodium": 650, "Protein": 22.0},
            "chicharron": {"Caloric Value": 540, "Fat": 44.0, "Saturated Fats": 16.0, "Sugars": 0.0, "Sodium": 690, "Protein": 32.0},
            "carne oreada": {"Caloric Value": 430, "Fat": 22.0, "Saturated Fats": 8.5, "Sugars": 0.5, "Sodium": 720, "Protein": 42.0},
            "arroz con pollo": {"Caloric Value": 460, "Fat": 14.0, "Saturated Fats": 3.8, "Sugars": 3.5, "Sodium": 610, "Protein": 26.0},
            "picada colombiana": {"Caloric Value": 820, "Fat": 52.0, "Saturated Fats": 19.5, "Sugars": 2.5, "Sodium": 1180, "Protein": 38.0},
            "mojarra frita": {"Caloric Value": 520, "Fat": 24.0, "Saturated Fats": 6.5, "Sugars": 2.0, "Sodium": 480, "Protein": 40.0},
            "calentado": {"Caloric Value": 550, "Fat": 18.0, "Saturated Fats": 6.2, "Sugars": 3.0, "Sodium": 590, "Protein": 24.0},
            "cazuela de frijoles": {"Caloric Value": 580, "Fat": 21.0, "Saturated Fats": 7.5, "Sugars": 6.0, "Sodium": 640, "Protein": 25.0},
            "ceviche": {"Caloric Value": 210, "Fat": 4.0, "Saturated Fats": 0.8, "Sugars": 3.0, "Sodium": 360, "Protein": 28.0},
            "lomo saltado": {"Caloric Value": 560, "Fat": 26.0, "Saturated Fats": 8.0, "Sugars": 4.0, "Sodium": 740, "Protein": 32.0},
            "asado": {"Caloric Value": 510, "Fat": 32.0, "Saturated Fats": 12.5, "Sugars": 0.5, "Sodium": 580, "Protein": 44.0},
            "choripan": {"Caloric Value": 490, "Fat": 28.0, "Saturated Fats": 10.5, "Sugars": 2.0, "Sodium": 820, "Protein": 20.0},
            "milanesa": {"Caloric Value": 440, "Fat": 22.0, "Saturated Fats": 6.5, "Sugars": 1.5, "Sodium": 540, "Protein": 31.0},
            "alfajor": {"Caloric Value": 280, "Fat": 12.0, "Saturated Fats": 6.8, "Sugars": 24.0, "Sodium": 110, "Protein": 3.5},
            "cachapa": {"Caloric Value": 410, "Fat": 16.0, "Saturated Fats": 8.5, "Sugars": 9.0, "Sodium": 420, "Protein": 14.0},
            "pabellon criollo": {"Caloric Value": 630, "Fat": 22.0, "Saturated Fats": 7.0, "Sugars": 11.0, "Sodium": 680, "Protein": 34.0},
            "feijoada": {"Caloric Value": 590, "Fat": 26.0, "Saturated Fats": 9.5, "Sugars": 2.5, "Sodium": 790, "Protein": 33.0},
            "coxinha": {"Caloric Value": 310, "Fat": 16.5, "Saturated Fats": 5.5, "Sugars": 1.5, "Sodium": 430, "Protein": 11.0},
            "anticuchos": {"Caloric Value": 340, "Fat": 15.0, "Saturated Fats": 5.0, "Sugars": 1.5, "Sodium": 510, "Protein": 35.0},
            "pollo asado": {"Caloric Value": 390, "Fat": 19.0, "Saturated Fats": 5.5, "Sugars": 0.5, "Sodium": 560, "Protein": 38.0}
        }

        # 3. Descripciones visuales para OpenAI CLIP
        self.descripciones_visuales_clip = {
            "salchipapa": "a plate of Latin American salchipapa with french fries, sliced red hot dog sausages, and mayonnaise and ketchup drizzled on top",
            "choripapa": "a plate of french fries topped with sliced grilled brown chorizo sausage and sauces",
            "empanada": "golden deep fried Latin American empanadas or turnovers made of corn or wheat dough",
            "arepa": "flat round grilled white or yellow cornmeal bread arepa",
            "arepa de huevo": "thick golden deep fried yellow corn arepa stuffed with egg",
            "arepa rellena": "grilled corn arepa split open and stuffed with shredded meat, chicken or melted cheese",
            "patacon": "flattened twice-fried crispy green plantain patacon or toston",
            "aborrajado": "battered deep fried sweet ripe plantain stuffed with white cheese",
            "buñuelo": "round golden-brown deep fried Colombian cheese dough balls bunuelos",
            "pandebono": "baked round golden Colombian cheese bread rolls pandebono or almojabana",
            "deditos de queso": "fried rolled pastry dough sticks stuffed with cheese tequenos",
            "papa rellena": "round deep fried breaded mashed potato ball stuffed with meat",
            "perro caliente colombiano": "loaded Colombian hot dog in a bun topped with crushed potato chips, pineapple sauce, mayonnaise and ketchup",
            "mazorcada": "loaded yellow sweet corn kernels dish mixed with chopped meat, shredded chicken, melted cheese, potato sticks and sauces",
            "bandeja paisa": "large Colombian bandeja paisa platter with red beans, white rice, crispy pork belly chicharron, fried egg, sweet plantain, ground beef and avocado",
            "sancocho": "traditional Latin American sancocho soup in a bowl with corn on the cob, yuca, plantain, potato, broth and meat",
            "mute santandereano": "thick traditional Colombian soup with yellow corn, tripe, meat, potatoes, pasta and herbs",
            "ajiaco": "creamy yellow potato soup ajiaco with shredded chicken, corn on the cob, capers, white cream and avocado",
            "lechona": "Colombian roasted pork dish with yellow rice, peas, shredded pork meat and crispy pork skin",
            "tamal": "traditional Latin American tamal cooked and served on a green banana leaf",
            "tamal santandereano": "traditional cylindrical Colombian tamal santandereano made of yellow cornmeal dough stuffed with meat, chickpeas, raisins and capers, wrapped in green plantain leaf",
            "chicharron": "crispy fried pork belly strip chicharron with multi-layered meat and crunchy skin",
            "carne oreada": "grilled marinated beef steak carne asada served with yuca or arepa",
            "arroz con pollo": "Latin American yellow rice mixed with shredded chicken, peas, carrots and bell peppers",
            "picada colombiana": "shared platter of assorted fried meats, chorizo, black blood sausage morcilla, chicharron, yellow creole potatoes and plantain",
            "mojarra frita": "whole deep fried tilapia or mojarra fish served on a plate with patacon, salad and coconut rice",
            "calentado": "Colombian breakfast plate of mixed rice and red beans served with a fried egg and arepa",
            "cazuela de frijoles": "bowl of red beans stew topped with diced fried pork, sweet plantain, avocado and corn",
            "ceviche": "raw fish or shrimp ceviche marinated in lime juice with sliced red onions, cilantro, corn and sweet potato",
            "lomo saltado": "Peruvian stir-fry of beef strips, red onions, tomatoes, soy sauce and french fries served with white rice",
            "asado": "South American grilled beef steaks and sausages on a barbecue grill or wooden board",
            "choripan": "grilled chorizo sausage sandwich in crusty baguette bread with green chimichurri sauce",
            "milanesa": "thin breaded pan-fried beef or chicken cutlet milanesa on a plate",
            "alfajor": "round South American cookie sandwich filled with dulce de leche caramel and coated in chocolate or coconut",
            "cachapa": "folded thick yellow sweet corn pancake filled with white cheese",
            "pabellon criollo": "plate with white rice, shredded beef stew, black beans and fried sweet plantains",
            "feijoada": "Brazilian black bean and pork stew served with white rice and orange slices",
            "coxinha": "teardrop-shaped breaded deep fried chicken croquette",
            "anticuchos": "grilled meat skewers on wooden sticks",
            "pollo asado": "rotisserie roasted chicken with golden seasoned skin",
            "apple": "a fresh whole red or green apple fruit",
            "banana": "a yellow banana fruit",
            "orange": "a fresh orange citrus fruit",
            "strawberries": "fresh red strawberries",
            "watermelon": "sliced red watermelon fruit",
            "pineapple": "fresh yellow pineapple fruit",
            "mango": "fresh mango fruit",
            "avocado": "green avocado cut in half showing the pit",
            "salad": "bowl of fresh green vegetable salad with lettuce, tomato and cucumber",
            "salmon": "cooked pink salmon fish fillet on a plate",
            "sushi": "Japanese sushi rolls with rice, seaweed and raw fish",
            "chicken breast": "plain grilled chicken breast fillet on a plate",
            "fried chicken": "crispy breaded deep fried chicken pieces",
            "egg": "cooked fried egg or boiled egg",
            "omelette": "folded yellow egg omelette on a plate",
            "rice": "bowl or plate of plain cooked white rice",
            "spaghetti": "plate of spaghetti pasta with red tomato sauce",
            "lasagna": "baked layered pasta lasagna with cheese and meat sauce",
            "ramen": "bowl of Asian noodle soup ramen with broth and toppings",
            "hamburger": "burger sandwich with beef patty, cheese, lettuce, tomato and bun",
            "pizza": "baked pizza with melted mozzarella cheese, tomato sauce and pepperoni",
            "french fries": "plain golden french fries potato sticks without sausages",
            "hot dog": "plain American hot dog sausage in a long bun without potato chips",
            "sandwich": "sliced bread sandwich with ham, cheese and lettuce",
            "tacos": "Mexican folded corn tortillas filled with meat, onion and cilantro",
            "nachos": "triangular tortilla chips topped with melted yellow cheese and jalapenos",
            "waffles": "sweet breakfast Belgian waffle with square grid pockets, maple syrup and fruit, without sausages",
            "pancakes": "stack of round flat breakfast pancakes with butter and syrup",
            "donuts": "round glazed ring donuts with sprinkles",
            "churros": "fried ridged dough pastry sticks churros dusted with sugar",
            "chocolate cake": "slice of dark chocolate cake with frosting",
            "ice cream": "scoops of cold ice cream in a bowl or cone",
            "bread": "loaf or slices of baked bread"
        }

        self.cargar_memoria_extra()
        self.cargar_huellas_visuales()
        self.clip_model = None
        self.clip_processor = None
        if IA_PESADA_DISPONIBLE:
            self.dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
            self.cargar_modelo_local()
        else:
            self.dispositivo = "cpu"

    def cargar_memoria_extra(self):
        if os.path.exists(self.archivo_extra_json):
            try:
                with open(self.archivo_extra_json, "r", encoding="utf-8") as f:
                    guardados = json.load(f)
                    self.catalogo_latino.update(guardados)
                    for plato in guardados:
                        if plato not in self.descripciones_visuales_clip:
                            self.descripciones_visuales_clip[plato] = f"a photo of a plate of food called {plato}, traditional meal"
            except Exception:
                pass

    def guardar_en_memoria_extra(self, nombre, datos_nutricionales):
        self.catalogo_latino[nombre] = datos_nutricionales
        try:
            with open(self.archivo_extra_json, "w", encoding="utf-8") as f:
                json.dump(self.catalogo_latino, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def cargar_huellas_visuales(self):
        if os.path.exists(self.archivo_huellas_visuales):
            try:
                with open(self.archivo_huellas_visuales, "r", encoding="utf-8") as f:
                    self.huellas_visuales = json.load(f)
            except Exception:
                self.huellas_visuales = {}

    def guardar_huellas_visuales(self):
        try:
            with open(self.archivo_huellas_visuales, "w", encoding="utf-8") as f:
                json.dump(self.huellas_visuales, f)
        except Exception:
            pass

    def cargar_modelo_local(self):
        if not IA_PESADA_DISPONIBLE:
            return
        carpeta_entrenada = os.path.join(self.carpeta_csv, "modelo_nutrixion_entrenado")
        nombre_modelo = carpeta_entrenada if os.path.exists(os.path.join(carpeta_entrenada, "config.json")) else "openai/clip-vit-base-patch32"
        print("🧠 Cargando motor de visión IA CLIP...")
        try:
            self.clip_processor = CLIPProcessor.from_pretrained(nombre_modelo)
            self.clip_model = CLIPModel.from_pretrained(nombre_modelo).to(self.dispositivo)
            self.clip_model.eval()
            print(f"✅ Motor CLIP listo en modo {self.dispositivo.upper()}.")
        except Exception as e:
            print(f"❌ Error al cargar el modelo CLIP: {e}")
            self.clip_model = None

    def _extraer_vector_imagen(self, imagen_pil):
        inputs_img = self.clip_processor(images=imagen_pil, return_tensors="pt")
        pixel_values = inputs_img["pixel_values"].to(self.dispositivo)

        with torch.no_grad():
            salida = self.clip_model.get_image_features(pixel_values=pixel_values)

            if isinstance(salida, torch.Tensor):
                emb = salida
            elif hasattr(salida, "image_embeds") and salida.image_embeds is not None:
                emb = salida.image_embeds
            elif hasattr(salida, "pooler_output") and salida.pooler_output is not None:
                emb = salida.pooler_output
                if hasattr(self.clip_model, "visual_projection") and emb.shape[-1] == self.clip_model.visual_projection.in_features:
                    emb = self.clip_model.visual_projection(emb)
            else:
                emb = salida[0]

            emb = torch.nn.functional.normalize(emb, p=2, dim=-1)

        return emb[0].detach().cpu()

    def entrenar_comida_desde_imagenes(self, nombre_comida, lista_rutas_imagenes, nutrientes_dict, descripcion_visual=""):
        if not IA_PESADA_DISPONIBLE or not self.clip_model or not self.clip_processor:
            return {"error": "El motor CLIP solo está disponible en PC."}

        nombre_limpio = nombre_comida.lower().strip()
        vectores = []

        if nombre_limpio in self.huellas_visuales:
            vectores.append(torch.tensor(self.huellas_visuales[nombre_limpio], dtype=torch.float32))

        fotos_procesadas = 0
        for ruta in lista_rutas_imagenes:
            if ruta and os.path.exists(ruta):
                try:
                    img = Image.open(ruta).convert("RGB")
                    vec = self._extraer_vector_imagen(img)
                    vectores.append(vec)
                    fotos_procesadas += 1
                except Exception:
                    pass

        if not vectores:
            return {"error": "No se pudieron procesar las imágenes seleccionadas."}

        vector_promedio = torch.stack(vectores).mean(dim=0)
        vector_promedio = torch.nn.functional.normalize(vector_promedio, p=2, dim=-1)
        self.huellas_visuales[nombre_limpio] = vector_promedio.tolist()
        self.guardar_huellas_visuales()

        if descripcion_visual.strip():
            self.descripciones_visuales_clip[nombre_limpio] = f"a photo of {nombre_limpio}, {descripcion_visual.strip()}, food dish"
        elif nombre_limpio not in self.descripciones_visuales_clip:
            self.descripciones_visuales_clip[nombre_limpio] = f"a photo of a plate of food called {nombre_limpio}, traditional meal"

        self.guardar_en_memoria_extra(nombre_limpio, nutrientes_dict)
        return {"exito": True, "nombre": nombre_limpio, "fotos": fotos_procesadas}

    def deducir_nutrientes_desde_imagenes_ia(self, nombre_comida, lista_rutas_imagenes):
        nombre_limpio = nombre_comida.lower().strip()

        if nombre_limpio in self.catalogo_latino:
            base = self.catalogo_latino[nombre_limpio].copy()
            return base, self._generar_tabla_porciones(base)

        acumulado = {
            "Caloric Value": 0.0,
            "Fat": 0.0,
            "Saturated Fats": 0.0,
            "Sugars": 0.0,
            "Sodium": 0.0,
            "Protein": 0.0
        }
        peso_total = 0.0

        if IA_PESADA_DISPONIBLE and self.clip_model and self.clip_processor:
            nombres_platos = list(self.descripciones_visuales_clip.keys())
            textos_descriptivos = list(self.descripciones_visuales_clip.values())

            for ruta in lista_rutas_imagenes:
                if not os.path.exists(ruta):
                    continue
                try:
                    imagen = Image.open(ruta).convert("RGB")
                    inputs = self.clip_processor(
                        text=textos_descriptivos,
                        images=imagen,
                        return_tensors="pt",
                        padding=True,
                        truncation=True
                    ).to(self.dispositivo)

                    with torch.no_grad():
                        outputs = self.clip_model(**inputs)
                        probs = outputs.logits_per_image.softmax(dim=1)[0]

                    top_probs, top_indices = torch.topk(probs, k=min(5, len(nombres_platos)))

                    for prob, idx in zip(top_probs, top_indices):
                        etiqueta = nombres_platos[idx.item()]
                        score = float(prob.item())

                        if etiqueta in self.catalogo_latino:
                            ref = self.catalogo_latino[etiqueta]
                            for k in acumulado:
                                acumulado[k] += float(ref[k]) * score
                            peso_total += score
                        else:
                            fila = self.buscar_en_csv(etiqueta, exacto=False)
                            if fila:
                                for k in acumulado:
                                    acumulado[k] += float(fila.get(k, 0)) * score
                                peso_total += score
                except Exception:
                    pass

        if peso_total > 0:
            nutrientes_ia = {k: round(v / peso_total, 1) for k, v in acumulado.items()}
            nutrientes_ia["Caloric Value"] = round(nutrientes_ia["Caloric Value"], 1)
            nutrientes_ia["Sodium"] = round(nutrientes_ia["Sodium"], 1)
        else:
            nutrientes_ia, _ = self.estimar_nutrientes_con_ia(nombre_limpio)

        if any(p in nombre_limpio for p in ["tamal", "envuelto", "hallaca", "pastel"]):
            nutrientes_ia["Caloric Value"] = round((nutrientes_ia["Caloric Value"] + 490) / 2, 1)
            nutrientes_ia["Fat"] = round((nutrientes_ia["Fat"] + 23.0) / 2, 1)
            nutrientes_ia["Protein"] = round((nutrientes_ia["Protein"] + 21.0) / 2, 1)
        elif any(p in nombre_limpio for p in ["frit", "chicharron", "salchipapa", "choripapa", "empanada", "papa"]):
            nutrientes_ia["Fat"] = round(max(nutrientes_ia["Fat"], 18.5), 1)
            nutrientes_ia["Saturated Fats"] = round(max(nutrientes_ia["Saturated Fats"], 7.5), 1)

        return nutrientes_ia, self._generar_tabla_porciones(nutrientes_ia)

    def _generar_tabla_porciones(self, nutrientes_base):
        tabla = {}
        for nombre_porcion, factor in self.factores_porcion.items():
            tabla[nombre_porcion] = {
                "Caloric Value": round(nutrientes_base["Caloric Value"] * factor, 1),
                "Fat": round(nutrientes_base["Fat"] * factor, 1),
                "Saturated Fats": round(nutrientes_base["Saturated Fats"] * factor, 1),
                "Protein": round(nutrientes_base["Protein"] * factor, 1),
                "Sugars": round(nutrientes_base["Sugars"] * factor, 1),
                "Sodium": round(nutrientes_base["Sodium"] * factor, 1)
            }
        return tabla

    def cargar_multiples_csv(self):
        """Lee los 5 archivos FOOD-DATA-GROUP*.csv con la librería estándar de Python (sin pandas)."""
        patron_busqueda = os.path.join(self.carpeta_csv, "FOOD-DATA-GROUP*.csv")
        archivos_csv = sorted(glob.glob(patron_busqueda))
        filas_totales = []
        columnas_numericas = {'Caloric Value', 'Fat', 'Saturated Fats', 'Sugars', 'Sodium', 'Protein'}

        for archivo in archivos_csv:
            try:
                with open(archivo, mode="r", encoding="utf-8", errors="ignore") as f:
                    lector = csv.DictReader(f)
                    for fila in lector:
                        item = {}
                        for k, v in fila.items():
                            if not k or "Unnamed" in k:
                                continue
                            clave = k.strip()
                            val_str = str(v).strip() if v is not None else ""
                            if clave == "food":
                                item["food"] = val_str.lower()
                            elif clave in columnas_numericas:
                                try:
                                    item[clave] = float(val_str.replace(",", "")) if val_str else 0.0
                                except ValueError:
                                    item[clave] = 0.0
                        if item.get("food"):
                            filas_totales.append(item)
            except Exception:
                pass

        return filas_totales

    def buscar_en_csv(self, termino, exacto=False):
        termino = termino.lower().strip()
        if not termino or not self.df:
            return None

        if exacto:
            patron = re.compile(rf"\b{re.escape(termino)}\b")
            for fila in self.df:
                if patron.search(fila["food"]):
                    return fila

        for fila in self.df:
            if termino in fila["food"]:
                return fila
        return None

    def identificar_imagen_con_ia(self, ruta_imagen):
        if not IA_PESADA_DISPONIBLE or not self.clip_model or not self.clip_processor:
            nombre_archivo = os.path.splitext(os.path.basename(ruta_imagen))[0].replace("_", " ").replace("-", " ").lower()
            for plato in self.catalogo_latino:
                if plato in nombre_archivo:
                    return {"alimento_en": plato, "confianza": 95.0, "porcion_detectada": "Mediana"}
            return {"error": "📱 En Android escribe el nombre del plato abajo y presiona 'Analizar Nutrientes'."}

        try:
            imagen = Image.open(ruta_imagen).convert("RGB")

            nombres_tamanos = list(self.prompts_tamano_clip.keys())
            textos_tamanos = list(self.prompts_tamano_clip.values())
            inputs_tamano = self.clip_processor(
                text=textos_tamanos, images=imagen, return_tensors="pt", padding=True, truncation=True
            ).to(self.dispositivo)

            with torch.no_grad():
                outputs_tamano = self.clip_model(**inputs_tamano)
                probs_tamano = outputs_tamano.logits_per_image.softmax(dim=1)[0]

            idx_tamano = int(torch.argmax(probs_tamano).item())
            porcion_detectada = nombres_tamanos[idx_tamano]

            mejor_plato_visual = None
            mayor_similitud_visual = 0.0

            if self.huellas_visuales:
                vector_actual = self._extraer_vector_imagen(imagen)
                for plato_aprendido, vec_guardado in self.huellas_visuales.items():
                    tensor_guardado = torch.tensor(vec_guardado, dtype=torch.float32)
                    similitud = float(torch.dot(vector_actual, tensor_guardado).item())
                    if similitud > mayor_similitud_visual:
                        mayor_similitud_visual = similitud
                        mejor_plato_visual = plato_aprendido

            nombres_platos = list(self.descripciones_visuales_clip.keys())
            textos_descriptivos = list(self.descripciones_visuales_clip.values())

            inputs_plato = self.clip_processor(
                text=textos_descriptivos, images=imagen, return_tensors="pt", padding=True, truncation=True
            ).to(self.dispositivo)

            with torch.no_grad():
                outputs_plato = self.clip_model(**inputs_plato)
                probs_plato = outputs_plato.logits_per_image.softmax(dim=1)[0]

            top_probs, top_indices = torch.topk(probs_plato, k=min(5, len(nombres_platos)))

            self.ultimas_predicciones_ia = []
            for prob, idx in zip(top_probs, top_indices):
                etiqueta = nombres_platos[idx.item()]
                score = float(prob.item())
                self.ultimas_predicciones_ia.append({"label": etiqueta, "score": score})

            if mejor_plato_visual and mayor_similitud_visual >= 0.80:
                mejor_plato = mejor_plato_visual
                confianza = round(min(mayor_similitud_visual * 100, 99.5), 1)
                self.ultimas_predicciones_ia.insert(0, {"label": mejor_plato, "score": mayor_similitud_visual})
            else:
                mejor_plato = self.ultimas_predicciones_ia[0]["label"]
                confianza = round(self.ultimas_predicciones_ia[0]["score"] * 100, 1)

            return {
                "alimento_en": mejor_plato,
                "confianza": confianza,
                "porcion_detectada": porcion_detectada
            }

        except Exception as e:
            return {"error": f"No se pudo procesar la imagen: {e}"}

    def estimar_nutrientes_con_ia(self, nombre_alimento):
        nombre_limpio = nombre_alimento.lower().strip()

        for clave, valores in self.catalogo_latino.items():
            if clave == nombre_limpio or clave in nombre_limpio or nombre_limpio in clave:
                return valores.copy(), "🇨🇴 Base Nutricional"

        acumulado = {"Caloric Value": 0.0, "Fat": 0.0, "Saturated Fats": 0.0, "Sugars": 0.0, "Sodium": 0.0, "Protein": 0.0}
        peso_total = 0.0

        if self.ultimas_predicciones_ia:
            for pred in self.ultimas_predicciones_ia:
                etiqueta = pred['label']
                score = float(pred['score'])

                if etiqueta in self.catalogo_latino:
                    ref = self.catalogo_latino[etiqueta]
                    for k in acumulado:
                        acumulado[k] += ref[k] * score
                    peso_total += score
                else:
                    fila = self.buscar_en_csv(etiqueta, exacto=False)
                    if fila:
                        for k in acumulado:
                            acumulado[k] += float(fila.get(k, 0)) * score
                        peso_total += score

        if peso_total > 0:
            estimacion = {k: round(v / peso_total, 1) for k, v in acumulado.items()}
            estimacion["Caloric Value"] = round(estimacion["Caloric Value"])
            self.guardar_en_memoria_extra(nombre_limpio, estimacion)
            return estimacion, "🧠 Calculado por IA"

        if any(p in nombre_limpio for p in ["frit", "salchipapa", "choripapa", "empanada", "chicharron", "papas", "buñuelo", "patacon"]):
            estimacion = {"Caloric Value": 420, "Fat": 24.0, "Saturated Fats": 9.5, "Sugars": 2.5, "Sodium": 580, "Protein": 12.0}
        elif any(p in nombre_limpio for p in ["sopa", "caldo", "sancocho", "mute", "ajiaco", "cazuela"]):
            estimacion = {"Caloric Value": 460, "Fat": 15.0, "Saturated Fats": 5.2, "Sugars": 3.5, "Sodium": 590, "Protein": 28.0}
        elif any(p in nombre_limpio for p in ["ensalada", "fruta", "verdura", "vegetal", "natural"]):
            estimacion = {"Caloric Value": 120, "Fat": 2.5, "Saturated Fats": 0.4, "Sugars": 6.0, "Sodium": 85, "Protein": 3.5}
        else:
            estimacion = {"Caloric Value": 310, "Fat": 12.0, "Saturated Fats": 4.2, "Sugars": 3.0, "Sodium": 380, "Protein": 15.0}

        self.guardar_en_memoria_extra(nombre_limpio, estimacion)
        return estimacion, "🧠 Estimado por IA"

    def calcular_perfil_usuario(self, peso_kg, altura_m):
        imc = peso_kg / (altura_m ** 2)
        
        if imc < 18.5:
            estado_peso = "Bajo peso (Meta: Superávit nutritivo)"
            calorias_diarias = peso_kg * 35
            limite_grasa = 25.0
            proteina_diaria = peso_kg * 1.8
            azucar_diaria = 32.0
        elif 18.5 <= imc < 25:
            estado_peso = "Peso saludable (Meta: Mantenimiento)"
            calorias_diarias = peso_kg * 30
            limite_grasa = 20.0
            proteina_diaria = peso_kg * 1.5
            azucar_diaria = 28.0
        else:
            estado_peso = "Sobrepeso / Obesidad (Meta: Déficit controlado)"
            calorias_diarias = peso_kg * 24
            limite_grasa = 14.0
            proteina_diaria = peso_kg * 1.4
            azucar_diaria = 22.0

        grasa_total_diaria = (calorias_diarias * 0.28) / 9.0
        grasa_sat_diaria = (calorias_diarias * 0.08) / 9.0
        sodio_diario = 2000.0
        limite_calorias_comida = calorias_diarias * 0.35

        return {
            "imc": round(imc, 2),
            "estado": estado_peso,
            "calorias_diarias_rec": round(calorias_diarias),
            "max_calorias_por_comida": round(limite_calorias_comida),
            "max_grasa_por_comida": limite_grasa,
            "base_diaria": {
                "Calorías": calorias_diarias,
                "Grasas Totales": grasa_total_diaria,
                "Grasas Saturadas": grasa_sat_diaria,
                "Azúcares": azucar_diaria,
                "Proteínas": proteina_diaria,
                "Sodio": sodio_diario
            }
        }

    def calcular_habitos_periodos(self, peso_kg, altura_m):
        perfil = self.calcular_perfil_usuario(peso_kg, altura_m)
        base = perfil["base_diaria"]
        factores = {"Diario": 1, "Semanal": 7, "Mensual": 30, "Anual": 365}

        periodos = {}
        for nombre_periodo, dias in factores.items():
            periodos[nombre_periodo] = {
                "Calorías": f"{round(base['Calorías'] * dias):,} kcal",
                "Grasas Totales": f"{round(base['Grasas Totales'] * dias, 1):,} g",
                "Grasas Saturadas": f"{round(base['Grasas Saturadas'] * dias, 1):,} g",
                "Azúcares": f"{round(base['Azúcares'] * dias, 1):,} g",
                "Proteínas": f"{round(base['Proteínas'] * dias, 1):,} g",
                "Sodio": f"{round(base['Sodio'] * dias):,} mg"
            }

        return {
            "imc": perfil["imc"],
            "estado": perfil["estado"],
            "max_calorias_por_comida": perfil["max_calorias_por_comida"],
            "max_grasa_por_comida": perfil["max_grasa_por_comida"],
            "periodos": periodos
        }

    def evaluar_alimento(self, nombre_comida_input, peso_kg, altura_m, ya_en_ingles=False, tamano_porcion="Mediana"):
        nombre_comida_input = nombre_comida_input.lower().strip()
        factor = self.factores_porcion.get(tamano_porcion, 1.0)

        plato_latino_detectado = None
        if nombre_comida_input in self.catalogo_latino:
            plato_latino_detectado = nombre_comida_input
        else:
            for clave in self.catalogo_latino:
                if clave in nombre_comida_input or nombre_comida_input in clave:
                    plato_latino_detectado = clave
                    break

        if plato_latino_detectado:
            datos = self.catalogo_latino[plato_latino_detectado]
            fuente_datos = ""
            nombre_mostrar = plato_latino_detectado.capitalize()
        else:
            if ya_en_ingles or MyMemoryTranslator is None:
                nombre_comida_en = nombre_comida_input
            else:
                try:
                    traductor_en = MyMemoryTranslator(source='es-ES', target='en-US')
                    nombre_comida_en = traductor_en.translate(nombre_comida_input).lower().strip()
                except Exception:
                    nombre_comida_en = nombre_comida_input

            fila_encontrada = self.buscar_en_csv(nombre_comida_en, exacto=True)
            if not fila_encontrada:
                fila_encontrada = self.buscar_en_csv(nombre_comida_en, exacto=False)

            if fila_encontrada:
                datos = fila_encontrada
                fuente_datos = ""
                nombre_mostrar = str(datos['food']).capitalize()
                if MyMemoryTranslator is not None:
                    try:
                        traductor_es = MyMemoryTranslator(source='en-US', target='es-ES')
                        nombre_mostrar = traductor_es.translate(nombre_mostrar).capitalize()
                    except Exception:
                        pass
            else:
                datos, fuente_datos = self.estimar_nutrientes_con_ia(nombre_comida_input)
                nombre_mostrar = nombre_comida_input.capitalize()

        perfil = self.calcular_perfil_usuario(peso_kg, altura_m)

        calorias = round(float(datos.get('Caloric Value', 0)) * factor, 1)
        grasas = round(float(datos.get('Fat', 0)) * factor, 1)
        grasas_sat = round(float(datos.get('Saturated Fats', 0)) * factor, 1)
        azucares = round(float(datos.get('Sugars', 0)) * factor, 1)
        sodio = round(float(datos.get('Sodium', 0)) * factor, 1)
        proteina = round(float(datos.get('Protein', 0)) * factor, 1)

        es_sobreprocesada = (
            (grasas_sat >= 7.0) or 
            (grasas >= 16.0 and calorias >= 280) or 
            (azucares > 22.0) or 
            (sodio > 0.6 and sodio < 50) or 
            (sodio > 400)
        )
        excede_limites_usuario = (calorias > perfil['max_calorias_por_comida']) or (grasas > perfil['max_grasa_por_comida'])

        if es_sobreprocesada or excede_limites_usuario:
            boton_color = "ROJO"
            boton_texto = "🔴 COMIDA SOBREPROCESADA / ALTA EN GRASA"
        else:
            boton_color = "VERDE"
            boton_texto = "🟢 COMIDA SALUDABLE"

        return {
            "alimento_encontrado": nombre_mostrar,
            "tamano_porcion": tamano_porcion,
            "fuente": fuente_datos,
            "nutricion": {
                "Calorías": f"{calorias} kcal",
                "Grasas Totales": f"{grasas} g",
                "Grasas Saturadas": f"{grasas_sat} g",
                "Azúcares": f"{azucares} g",
                "Proteínas": f"{proteina} g",
                "Sodio": f"{sodio} mg"
            },
            "perfil_usuario": perfil,
            "boton_color": boton_color,
            "boton_mensaje": boton_texto,
            "es_saludable": (boton_color == "VERDE")
        }

    def analizar_patron_y_conexiones(self, comidas_hoy, peso_kg, altura_m):
        perfil = self.calcular_perfil_usuario(peso_kg, altura_m)
        meta_diaria = perfil["calorias_diarias_rec"]

        if not comidas_hoy:
            return {
                "patron_titulo": "⏳ Patrón en observación (Sin registros aún)",
                "patron_color": "GREY",
                "patron_detalle": (
                    "Registra tus alimentos en la pestaña 'Identificar' indicando si son del "
                    "Desayuno, Almuerzo, Cena o Snack para detectar tu patrón alimenticio."
                ),
                "conexion_emocional": "Aún no hay comidas vinculadas con estados de fatiga, malestar o ánimo."
            }

        total_kcal = sum(c["kcal"] for c in comidas_hoy)
        total_comidas = len(comidas_hoy)
        rojas = sum(1 for c in comidas_hoy if not c.get("es_saludable", True))
        horarios = [c.get("horario", "Almuerzo") for c in comidas_hoy]
        snacks = sum(1 for h in horarios if h == "Snack")

        if rojas > (total_comidas / 2) or (rojas >= 2 and total_kcal > meta_diaria * 0.8):
            patron_titulo = "🔴 Patrón Inadecuado (Alto en Ultraprocesados / Grasas)"
            patron_color = "RED"
            patron_detalle = (
                f"De {total_comidas} comida(s) hoy, {rojas} superan los límites de grasa/sodio. "
                "Este patrón predispone a inflamación digestiva, pesadez y fatiga postprandial."
            )
        elif ("Desayuno" not in horarios and ("Cena" in horarios or snacks >= 2)) or (snacks > total_comidas / 2) or any(c["kcal"] > meta_diaria * 0.55 for c in comidas_hoy):
            patron_titulo = "🟠 Patrón Desorganizado (Desbalance Horario / Picoteo)"
            patron_color = "ORANGE"
            patron_detalle = (
                "Se detecta omisión de comidas principales (como el desayuno) o concentración "
                "excesiva de calorías en un solo momento/snacks, provocando picos y caídas de energía."
            )
        elif total_kcal < (meta_diaria * 0.45):
            patron_titulo = "🟡 Patrón Restrictivo / Subalimentación"
            patron_color = "AMBER"
            patron_detalle = (
                f"Llevas {round(total_kcal):,} kcal de una meta de {meta_diaria:,} kcal ({round((total_kcal/meta_diaria)*100)}%). "
                "Una ingesta tan baja limita la glucosa cerebral, causando fatiga y desmotivación."
            )
        else:
            patron_titulo = "🟢 Patrón Equilibrado y Saludable"
            patron_color = "GREEN"
            patron_detalle = (
                "Tus horarios, tamaños de porción y elecciones nutricionales están bien distribuidos hoy, "
                "favoreciendo niveles estables de energía, buena digestión y enfoque mental."
            )

        comidas_con_sintoma = [c for c in comidas_hoy if c.get("efecto", "Bien") != "Bien"]
        if not comidas_con_sintoma:
            conexion = "✅ Todas tus comidas registradas hoy están asociadas con bienestar físico (😊 Bien)."
        else:
            detalles_efecto = [f"{c['nombre']} ({c['efecto']})" for c in comidas_con_sintoma]
            rojas_con_sintoma = sum(1 for c in comidas_con_sintoma if not c.get("es_saludable", True))
            if rojas_con_sintoma > 0:
                conexion = (
                    f"⚠️ Conexión detectada: Reportaste malestar/fatiga tras consumir {', '.join(detalles_efecto)}. "
                    f"El {round((rojas_con_sintoma/len(comidas_con_sintoma))*100)}% de tus síntomas hoy proviene de alimentos marcados en ROJO."
                )
            else:
                conexion = (
                    f"🔍 Conexión detectada: Experimentaste síntomas en {', '.join(detalles_efecto)}. "
                    "Revisa tu hidratación, el tamaño de la porción o el déficit calórico acumulado."
                )

        return {
            "patron_titulo": patron_titulo,
            "patron_color": patron_color,
            "patron_detalle": patron_detalle,
            "conexion_emocional": conexion
        }

    def diagnosticar_sintoma(self, sintoma, peso_kg, altura_m, comidas_hoy):
        perfil = self.calcular_perfil_usuario(peso_kg, altura_m)
        meta_diaria = perfil["calorias_diarias_rec"]
        imc = perfil["imc"]
        consumidas = round(sum(item["kcal"] for item in comidas_hoy))
        nombres_comidas = [item["nombre"].lower() for item in comidas_hoy]
        comio_pesado = any(not item.get("es_saludable", True) for item in comidas_hoy)

        if sintoma == "Fatiga":
            if consumidas == 0:
                causa = f"Déficit energético por ayuno: Llevas 0 kcal hoy (meta: {meta_diaria:,} kcal). Tu cuerpo carece de glucosa inmediata."
            elif consumidas < (meta_diaria * 0.40):
                causa = f"Patrón restrictivo actual: Solo llevas {consumidas:,} kcal de {meta_diaria:,} kcal hoy, reduciendo tu energía celular."
            elif comio_pesado:
                causa = "Fatiga postprandial: El consumo de porciones densas en grasa hoy sobrecarga la digestión y produce somnolencia."
            else:
                causa = "Deshidratación celular leve o falta de micronutrientes (hierro/magnesio) entre comidas."

            return {
                "titulo": "⚡ Plan de Recuperación contra la Fatiga",
                "causa_nutricional": causa,
                "alimentos_recomendados": (
                    "• Banano o manzana (energía rápida + potasio)\n"
                    "• Avena, arroz o arepa asada (carbohidrato complejo sostenido)\n"
                    "• Huevo cocido o frutos secos + 2 vasos de agua pura"
                ),
                "solucion_inmediata": (
                    "1. Bebe un vaso grande de agua inmediatamente.\n"
                    "2. Evita azúcares refinados (generan rebote de cansancio).\n"
                    "3. Realiza 5 minutos de estiramiento y respiración profunda."
                )
            }

        elif sintoma == "Malestar":
            if comio_pesado:
                causa = f"Sobrecarga digestiva por patrón inadecuado: Ingeriste alimentos altos en grasa/sodio hoy ({', '.join(nombres_comidas)})."
            elif consumidas == 0:
                causa = "Irritación gástrica por ayuno prolongado: El ácido estomacal actúa sobre el estómago vacío."
            elif consumidas > meta_diaria:
                causa = f"Exceso volumétrico y calórico ({consumidas:,} / {meta_diaria:,} kcal), generando distensión abdominal."
            else:
                causa = "Sensibilidad digestiva por comer rápido, falta de fibra soluble o baja hidratación."

            return {
                "titulo": "🤢 Plan de Alivio para el Malestar",
                "causa_nutricional": causa,
                "alimentos_recomendados": (
                    "• Infusión tibia de manzanilla, hierbabuena o jengibre\n"
                    "• Caldo claro de pollo desgrasado o arroz blanco suave\n"
                    "• Papaya o manzana sin cáscara (enzimas digestivas)"
                ),
                "solucion_inmediata": (
                    "1. Suspende frituras, salsas, lácteos enteros y picantes por hoy.\n"
                    "2. Toma líquidos tibios en sorbos lentos y elige porciones pequeñas.\n"
                    "3. Mantén postura erguida al menos 30 minutos tras comer."
                )
            }

        else:
            if consumidas < (meta_diaria * 0.35):
                causa = f"Restricción energética ({consumidas:,} kcal hoy): El déficit severo reduce la síntesis de serotonina y dopamina cerebral."
            elif imc < 18.5 or imc >= 25:
                causa = f"Desgaste por metas físicas (IMC: {imc}): Los hábitos restrictivos o desorganizados generan frustración emocional."
            else:
                causa = "Déficit de triptófano, ácidos grasos Omega-3 o fatiga mental acumulada en la rutina."

            return {
                "titulo": "🌟 Plan de Impulso contra la Desmotivación",
                "causa_nutricional": causa,
                "alimentos_recomendados": (
                    "• Chocolate oscuro (+70% cacao) (estimula endorfinas)\n"
                    "• Aguacate, salmón o pescado (Omega-3 neuroprotector)\n"
                    "• Banano, huevos o pollo (precursores de serotonina)"
                ),
                "solucion_inmediata": (
                    "1. Meta mínima viable: Enfócate solo en sumar 1 comida saludable (🟢) hoy.\n"
                    "2. Camina 10 minutos con luz natural para activar dopamina.\n"
                    "3. Evita saltarte horarios de comida para estabilizar tu estado de ánimo."
                )
            }

    def calcular_efectividad_regulacion(self, comidas_hoy, origenes_identificados, habitos_modificados):
        if not comidas_hoy:
            calidad_elecciones = 0.0
            verdes = 0
        else:
            verdes = sum(1 for c in comidas_hoy if c.get("es_saludable", True))
            calidad_elecciones = (verdes / len(comidas_hoy)) * 40.0

        puntaje_origen = min(origenes_identificados * 15.0, 30.0)
        puntaje_modificacion = min(habitos_modificados * 15.0, 30.0)

        porcentaje_total = round(min(calidad_elecciones + puntaje_origen + puntaje_modificacion, 100.0))

        if porcentaje_total >= 75:
            nivel = "🌟 Regulación Nutricional Alta (Hábitos Conscientes)"
        elif porcentaje_total >= 40:
            nivel = "📈 Regulación en Progreso (Mejorando Conciencia y Hábitos)"
        else:
            nivel = "🌱 Nivel Inicial (Identifica tus comidas y aplica las soluciones)"

        return {
            "porcentaje": porcentaje_total,
            "progreso_decimal": porcentaje_total / 100.0,
            "nivel": nivel,
            "comidas_saludables": f"{verdes}/{len(comidas_hoy)}",
            "origenes_identificados": origenes_identificados,
            "habitos_modificados": habitos_modificados
        }