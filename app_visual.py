import flet as ft
import base64
import threading
import time
import json
import os
from motor_nutricional import AnalizadorNutricional

try:
    import cv2
except ImportError:
    cv2 = None

ARCHIVO_ESTADO = "estado_nutrixion.json"


def buscar_archivo_logo():
    """Busca automáticamente el logo guardado en la carpeta del proyecto."""
    posibles_nombres = [
        "logo.png", "logo.jpg", "logo.jpeg",
        "logo_nutrixion.png", "logo_nutrixion.jpg",
        "image_1.png", "watermarked_img_4370711781040816475.jpg"
    ]
    for nombre in posibles_nombres:
        if os.path.exists(nombre):
            return os.path.abspath(nombre)
    return None


def main(page: ft.Page):
    page.title = "NutriXion"
    page.window.width = 450
    page.window.height = 920
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0B0F19"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.padding = 0

    ruta_logo = buscar_archivo_logo()
    if ruta_logo:
        page.window.icon = ruta_logo

    estado_app = {
        "seccion_actual": "habitos",
        "periodo_actual": "Diario",
        "sintoma_actual": None,
        "horario_seleccionado": "Almuerzo",
        "porcion_seleccionada": "Mediana",
        "alimento_actual_raw": "",
        "ya_en_ingles_actual": False,
        "datos_calculados": None,
        "modo_oscuro": True,
        "comidas_hoy": [],
        "contador_id": 0,
        "ultimo_escaneo": None,
        "origenes_identificados": 0,
        "habitos_modificados": 0
    }

    def guardar_progreso():
        try:
            datos_guardar = {
                "modo_oscuro": estado_app["modo_oscuro"],
                "comidas_hoy": estado_app["comidas_hoy"],
                "contador_id": estado_app["contador_id"],
                "origenes_identificados": estado_app["origenes_identificados"],
                "habitos_modificados": estado_app["habitos_modificados"]
            }
            with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
                json.dump(datos_guardar, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def cargar_progreso():
        if os.path.exists(ARCHIVO_ESTADO):
            try:
                with open(ARCHIVO_ESTADO, "r", encoding="utf-8") as f:
                    datos = json.load(f)
                    estado_app["modo_oscuro"] = datos.get("modo_oscuro", True)
                    estado_app["comidas_hoy"] = datos.get("comidas_hoy", [])
                    estado_app["contador_id"] = datos.get("contador_id", 0)
                    estado_app["origenes_identificados"] = datos.get("origenes_identificados", 0)
                    estado_app["habitos_modificados"] = datos.get("habitos_modificados", 0)
            except Exception:
                pass

    cargar_progreso()

    # =========================================================================
    # PANTALLA DE CARGA ANIMADA (SPLASH SCREEN)
    # =========================================================================
    contenido_logo_splash = (
        ft.Image(src=ruta_logo, width=145, height=145, fit=ft.ImageFit.COVER, border_radius=73)
        if ruta_logo else ft.Text("🍏", size=68)
    )

    logo_animado = ft.Container(
        width=154,
        height=154,
        border_radius=77,
        bgcolor=ft.colors.TEAL_900 if ruta_logo else ft.colors.WHITE,
        border=ft.border.all(3, ft.colors.AMBER_400),
        alignment=ft.alignment.center,
        scale=0.3,
        opacity=0.0,
        animate_scale=ft.animation.Animation(750, ft.AnimationCurve.ELASTIC_OUT),
        animate_opacity=ft.animation.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
        content=contenido_logo_splash
    )

    titulo_splash = ft.Text(
        "NutriXion",
        size=38,
        weight=ft.FontWeight.BOLD,
        color=ft.colors.WHITE,
        opacity=0.0,
        animate_opacity=ft.animation.Animation(600, ft.AnimationCurve.EASE_OUT)
    )

    subtitulo_splash = ft.Text(
        "Salud alimenticia",
        size=16,
        weight=ft.FontWeight.W_500,
        color=ft.colors.AMBER_300,
        opacity=0.0,
        animate_opacity=ft.animation.Animation(700, ft.AnimationCurve.EASE_IN),
        text_align=ft.TextAlign.CENTER
    )

    barra_carga_splash = ft.ProgressBar(
        width=230,
        value=0.0,
        color=ft.colors.AMBER_400,
        bgcolor=ft.colors.GREEN_900,
        border_radius=10
    )

    texto_carga_splash = ft.Text(
        "Abriendo NutriXion...",
        size=12,
        color=ft.colors.WHITE70,
        italic=True
    )

    pantalla_splash = ft.Container(
        width=450,
        height=900,
        padding=ft.padding.only(top=40),
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=[ft.colors.TEAL_900, ft.colors.GREEN_900, ft.colors.TEAL_800]
        ),
        alignment=ft.alignment.center,
        animate_opacity=ft.animation.Animation(400, ft.AnimationCurve.EASE_IN_OUT),
        content=ft.Column(
            controls=[
                logo_animado,
                ft.Container(height=10),
                titulo_splash,
                subtitulo_splash,
                ft.Container(height=25),
                barra_carga_splash,
                texto_carga_splash
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8
        )
    )

    contenedor_principal_app = ft.Container(
        padding=ft.padding.only(left=12, top=38, right=12, bottom=24),
        visible=False
    )

    zona_segura = ft.SafeArea(
        minimum_padding=ft.padding.only(top=16, bottom=10),
        content=ft.Column(
            controls=[pantalla_splash, contenedor_principal_app],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0
        )
    )

    page.add(zona_segura)

    motor = AnalizadorNutricional(carpeta_csv=".")
    estado_camara = {"activa": False, "cap": None, "ruta_foto": None}

    # =========================================================================
    # CUADRÍCULA VISUAL DE NUTRIENTES (2x3 TARJETAS ADAPTABLES A MÓVIL)
    # =========================================================================
    meta_iconos_nutrientes = {
        "Calorías": ("🔥", ft.colors.ORANGE_700),
        "Proteínas": ("💪", ft.colors.BLUE_700),
        "Grasas Totales": ("🥑", ft.colors.GREEN_700),
        "Grasas Saturadas": ("🍔", ft.colors.RED_700),
        "Azúcares": ("🍬", ft.colors.PINK_600),
        "Sodio": ("🧂", ft.colors.TEAL_700)
    }

    def construir_grid_nutrientes(diccionario_nutrientes):
        es_osc = estado_app["modo_oscuro"]
        bg_chip = "#1E293B" if es_osc else "#F1F5F9"
        borde_chip = "#334155" if es_osc else "#CBD5E1"
        color_titulo = ft.colors.GREY_400 if es_osc else ft.colors.BLUE_GREY_700
        color_valor = ft.colors.WHITE if es_osc else ft.colors.BLACK87

        orden_claves = ["Calorías", "Proteínas", "Grasas Totales", "Grasas Saturadas", "Azúcares", "Sodio"]
        tarjetas = []

        for clave in orden_claves:
            valor = diccionario_nutrientes.get(clave, "0")
            emoji, color_acento = meta_iconos_nutrientes.get(clave, ("•", ft.colors.GREEN_700))

            chip = ft.Container(
                width=162,
                height=56,
                padding=ft.padding.symmetric(horizontal=8, vertical=6),
                border_radius=10,
                bgcolor=bg_chip,
                border=ft.border.all(1, borde_chip),
                content=ft.Row(
                    controls=[
                        ft.Container(
                            width=30,
                            height=30,
                            border_radius=8,
                            bgcolor=color_acento,
                            alignment=ft.alignment.center,
                            content=ft.Text(emoji, size=14)
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(clave, size=10, color=color_titulo, no_wrap=True),
                                ft.Text(str(valor), size=12, weight=ft.FontWeight.BOLD, color=color_valor, no_wrap=True)
                            ],
                            spacing=1,
                            alignment=ft.MainAxisAlignment.CENTER
                        )
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                )
            )
            tarjetas.append(chip)

        return ft.Column(
            controls=[
                ft.Row(controls=tarjetas[0:2], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row(controls=tarjetas[2:4], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row(controls=tarjetas[4:6], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ],
            spacing=8
        )

    # =========================================================================
    # ENCABEZADO SUPERIOR Y PESTAÑAS DE NAVEGACIÓN
    # =========================================================================
    icono_header = (
        ft.Container(
            width=52,
            height=52,
            border_radius=26,
            border=ft.border.all(2, ft.colors.AMBER_400),
            content=ft.Image(src=ruta_logo, width=48, height=48, fit=ft.ImageFit.COVER, border_radius=24)
        )
        if ruta_logo else ft.Text("🍏", size=34)
    )

    banner_encabezado = ft.Container(
        width=365,
        padding=ft.padding.symmetric(horizontal=14, vertical=10),
        border_radius=16,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=["#064E3B", "#0F766E", "#115E59"]
        ),
        border=ft.border.all(1, "#14B8A6"),
        content=ft.Row(
            controls=[
                icono_header,
                ft.Column(
                    controls=[
                        ft.Text("NutriXion", size=23, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, no_wrap=True),
                        ft.Text("Salud alimenticia", size=12, weight=ft.FontWeight.W_600, color=ft.colors.AMBER_300, no_wrap=True)
                    ],
                    spacing=2
                )
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12
        )
    )

    def crear_tab_nav(clave, texto, icono):
        ic = ft.Icon(icono, size=18, color=ft.colors.WHITE)
        tx = ft.Text(texto, size=11, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, no_wrap=True)
        cont = ft.Container(
            width=83,
            height=48,
            border_radius=12,
            bgcolor=ft.colors.GREEN_700,
            alignment=ft.alignment.center,
            on_click=lambda e, c=clave: cambiar_seccion(c),
            content=ft.Column(
                controls=[ic, tx],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2
            )
        )
        return {"contenedor": cont, "icono": ic, "texto": tx}

    tab_habitos = crear_tab_nav("habitos", "Hábitos", ft.icons.MONITOR_WEIGHT)
    tab_identificar = crear_tab_nav("identificar", "Identificar", ft.icons.CAMERA_ALT)
    tab_diagnostico = crear_tab_nav("diagnostico", "Diagnóstico", ft.icons.FAVORITE)
    tab_ajustes = crear_tab_nav("ajustes", "Ajustes", ft.icons.SETTINGS)

    mapa_tabs_nav = {
        "habitos": tab_habitos,
        "identificar": tab_identificar,
        "diagnostico": tab_diagnostico,
        "ajustes": tab_ajustes
    }

    contenedor_barra_nav = ft.Container(
        width=365,
        padding=4,
        border_radius=14,
        bgcolor="#111827",
        border=ft.border.all(1, "#1F2937"),
        content=ft.Row(
            controls=[
                tab_habitos["contenedor"],
                tab_identificar["contenedor"],
                tab_diagnostico["contenedor"],
                tab_ajustes["contenedor"]
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            spacing=3
        )
    )

    def aplicar_colores_navegacion():
        es_osc = estado_app["modo_oscuro"]
        contenedor_barra_nav.bgcolor = "#111827" if es_osc else "#E2E8F0"
        contenedor_barra_nav.border = ft.border.all(1, "#1F2937" if es_osc else "#CBD5E1")

        for clave, item in mapa_tabs_nav.items():
            activo = (clave == estado_app["seccion_actual"])
            if activo:
                item["contenedor"].bgcolor = ft.colors.GREEN_700
                item["icono"].color = ft.colors.WHITE
                item["texto"].color = ft.colors.WHITE
            else:
                item["contenedor"].bgcolor = "#1E293B" if es_osc else "#FFFFFF"
                item["icono"].color = ft.colors.GREY_400 if es_osc else ft.colors.BLUE_GREY_700
                item["texto"].color = ft.colors.GREY_400 if es_osc else ft.colors.BLUE_GREY_700

    def cambiar_seccion(seccion):
        estado_app["seccion_actual"] = seccion
        if seccion != "identificar":
            detener_camara()

        motor.cargar_memoria_extra()
        motor.cargar_huellas_visuales()

        vista_habitos.visible = (seccion == "habitos")
        vista_identificar.visible = (seccion == "identificar")
        vista_diagnostico.visible = (seccion == "diagnostico")
        vista_configuracion.visible = (seccion == "ajustes")

        actualizar_calculo_habitos()
        actualizar_tarjeta_restantes()
        actualizar_panel_diagnostico()
        if estado_app["sintoma_actual"]:
            mostrar_solucion_sintoma(estado_app["sintoma_actual"])
        aplicar_colores_navegacion()
        page.update()

    # =========================================================================
    # SECCIÓN 1: "HÁBITOS"
    # =========================================================================
    input_peso = ft.TextField(
        label="Peso (kg)",
        value="52.0",
        width=160,
        border_radius=10,
        keyboard_type=ft.KeyboardType.NUMBER,
        prefix_icon=ft.icons.SCALE,
        on_change=lambda e: actualizar_calculo_habitos()
    )
    input_altura = ft.TextField(
        label="Altura (m)",
        value="1.70",
        width=160,
        border_radius=10,
        keyboard_type=ft.KeyboardType.NUMBER,
        prefix_icon=ft.icons.HEIGHT,
        on_change=lambda e: actualizar_calculo_habitos()
    )

    tarjeta_perfil_inputs = ft.Container(
        width=365,
        padding=12,
        border_radius=14,
        bgcolor="#111827",
        border=ft.border.all(1, "#1F2937"),
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.icons.PERSON, color=ft.colors.TEAL_400, size=20),
                        ft.Text("Tu Perfil Físico y Metas", size=16, weight=ft.FontWeight.BOLD)
                    ],
                    spacing=8
                ),
                ft.Row(controls=[input_peso, input_altura], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ],
            spacing=10
        )
    )

    texto_resumen_imc = ft.Text("", size=13, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, text_align=ft.TextAlign.CENTER)
    tarjeta_imc_habitos = ft.Container(
        content=texto_resumen_imc,
        width=365,
        padding=12,
        border_radius=14,
        bgcolor=ft.colors.AMBER_800,
        alignment=ft.alignment.center
    )

    def crear_pastilla_periodo(nombre):
        txt = ft.Text(nombre, size=11, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, no_wrap=True)
        cont = ft.Container(
            width=82,
            height=36,
            border_radius=10,
            bgcolor=ft.colors.BLUE_800,
            alignment=ft.alignment.center,
            on_click=lambda e, n=nombre: seleccionar_periodo(n),
            content=txt
        )
        return {"contenedor": cont, "texto": txt}

    botones_periodo = {
        "Diario": crear_pastilla_periodo("Diario"),
        "Semanal": crear_pastilla_periodo("Semanal"),
        "Mensual": crear_pastilla_periodo("Mensual"),
        "Anual": crear_pastilla_periodo("Anual")
    }

    barra_periodos = ft.Container(
        width=365,
        padding=4,
        border_radius=12,
        bgcolor="#111827",
        border=ft.border.all(1, "#1F2937"),
        content=ft.Row(
            controls=[b["contenedor"] for b in botones_periodo.values()],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            spacing=3
        )
    )

    def aplicar_colores_periodo():
        es_osc = estado_app["modo_oscuro"]
        barra_periodos.bgcolor = "#111827" if es_osc else "#E2E8F0"
        barra_periodos.border = ft.border.all(1, "#1F2937" if es_osc else "#CBD5E1")

        for nombre, item in botones_periodo.items():
            if nombre == estado_app["periodo_actual"]:
                item["contenedor"].bgcolor = ft.colors.BLUE_700
                item["texto"].color = ft.colors.WHITE
            else:
                item["contenedor"].bgcolor = "#1E293B" if es_osc else "#FFFFFF"
                item["texto"].color = ft.colors.GREY_400 if es_osc else ft.colors.BLUE_GREY_800

    def seleccionar_periodo(nombre_periodo):
        estado_app["periodo_actual"] = nombre_periodo
        aplicar_colores_periodo()
        mostrar_datos_periodo()
        page.update()

    titulo_periodo_activo = ft.Text("", size=15, weight=ft.FontWeight.BOLD, color=ft.colors.GREEN_400)
    contenedor_grid_habitos = ft.Column(spacing=8)

    tarjeta_habitos_nutrientes = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.icons.ANALYTICS, color=ft.colors.GREEN_400, size=19),
                        titulo_periodo_activo
                    ],
                    spacing=8
                ),
                ft.Divider(height=6),
                contenedor_grid_habitos
            ],
            spacing=8
        ),
        padding=14,
        bgcolor="#111827",
        border=ft.border.all(1, ft.colors.GREEN_700),
        border_radius=14,
        width=365
    )

    indicador_meta_saludable = ft.Container(
        width=365,
        padding=12,
        border_radius=12,
        bgcolor=ft.colors.GREEN_800,
        alignment=ft.alignment.center,
        content=ft.Text("", size=12, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, text_align=ft.TextAlign.CENTER)
    )

    btn_ir_identificar = ft.ElevatedButton(
        text="Ir a Identificar Comida ➡️",
        width=365,
        height=44,
        on_click=lambda e: cambiar_seccion("identificar"),
        style=ft.ButtonStyle(
            bgcolor=ft.colors.BLUE_700,
            color=ft.colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=12)
        )
    )

    btn_ir_diagnostico = ft.ElevatedButton(
        text="Ver mi Diagnóstico y Plan de Recuperación 🩺",
        width=365,
        height=44,
        on_click=lambda e: cambiar_seccion("diagnostico"),
        style=ft.ButtonStyle(
            bgcolor=ft.colors.TEAL_700,
            color=ft.colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=12)
        )
    )

    def mostrar_datos_periodo():
        datos = estado_app["datos_calculados"]
        if not datos:
            return
        periodo = estado_app["periodo_actual"]
        nutrientes_periodo = datos["periodos"][periodo]

        titulo_periodo_activo.value = f"Recomendación {periodo} para ti"
        contenedor_grid_habitos.controls.clear()
        contenedor_grid_habitos.controls.append(construir_grid_nutrientes(nutrientes_periodo))

        indicador_meta_saludable.content.value = (
            f"🟢 META SALUDABLE POR COMIDA:\n"
            f"Máx. {datos['max_calorias_por_comida']} kcal  |  Máx. {datos['max_grasa_por_comida']} g de grasa"
        )

    def actualizar_calculo_habitos():
        try:
            peso = float(input_peso.value)
            altura = float(input_altura.value)
            if peso <= 0 or altura <= 0:
                raise ValueError
        except ValueError:
            texto_resumen_imc.value = "⚠️ Ingresa un peso y altura válidos."
            tarjeta_imc_habitos.bgcolor = ft.colors.RED_700
            page.update()
            return

        datos = motor.calcular_habitos_periodos(peso, altura)
        estado_app["datos_calculados"] = datos

        texto_resumen_imc.value = f"Tu IMC: {datos['imc']} — {datos['estado']}"
        if datos["imc"] < 18.5:
            tarjeta_imc_habitos.bgcolor = ft.colors.AMBER_800
        elif datos["imc"] < 25:
            tarjeta_imc_habitos.bgcolor = ft.colors.GREEN_700
        else:
            tarjeta_imc_habitos.bgcolor = ft.colors.DEEP_ORANGE_700

        mostrar_datos_periodo()
        page.update()

    vista_habitos = ft.Column(
        controls=[
            tarjeta_perfil_inputs,
            tarjeta_imc_habitos,
            ft.Text("Selecciona el periodo recomendado:", size=12, weight=ft.FontWeight.W_600),
            barra_periodos,
            tarjeta_habitos_nutrientes,
            indicador_meta_saludable,
            btn_ir_identificar,
            btn_ir_diagnostico
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10,
        visible=True
    )

    # =========================================================================
    # SECCIÓN 2: "IDENTIFICAR"
    # =========================================================================
    texto_calorias_restantes = ft.Text("", size=12, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, text_align=ft.TextAlign.CENTER)
    tarjeta_calorias_dia = ft.Container(
        content=texto_calorias_restantes,
        width=365,
        padding=12,
        border_radius=14,
        bgcolor=ft.colors.TEAL_800,
        alignment=ft.alignment.center
    )

    lista_visual_comidas = ft.Column(spacing=8)

    contenedor_registro_hoy = ft.Container(
        width=365,
        padding=12,
        border_radius=14,
        bgcolor="#111827",
        border=ft.border.all(1, "#1F2937"),
        visible=False,
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("📋 Comidas consumidas hoy:", size=13, weight=ft.FontWeight.BOLD),
                        ft.TextButton("Vaciar día", on_click=lambda e: vaciar_comidas_hoy())
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                ft.Text("Marca cómo te sentiste tras cada comida (😊 Bien, ⚡ Fatiga, 🤢 Malestar, 😔 Ánimo):", size=11, color=ft.colors.GREY_400),
                lista_visual_comidas
            ],
            spacing=6
        )
    )

    def calcular_total_consumido_hoy():
        return sum(item["kcal"] for item in estado_app["comidas_hoy"])

    def cambiar_efecto_comida(id_comida, nuevo_efecto):
        for item in estado_app["comidas_hoy"]:
            if item["id"] == id_comida:
                item["efecto"] = nuevo_efecto
                break
        guardar_progreso()
        reconstruir_lista_comidas_hoy()
        actualizar_panel_diagnostico()
        page.update()

    def agregar_comida_al_dia(nombre, kcal, es_saludable=True, horario=None, porcion="Mediana"):
        estado_app["contador_id"] += 1
        nuevo_id = estado_app["contador_id"]
        momento = horario if horario else estado_app["horario_seleccionado"]
        estado_app["comidas_hoy"].append({
            "id": nuevo_id,
            "nombre": nombre,
            "porcion": porcion,
            "kcal": kcal,
            "es_saludable": es_saludable,
            "horario": momento,
            "efecto": "Bien"
        })
        if estado_app["ultimo_escaneo"] and estado_app["ultimo_escaneo"]["nombre"] == nombre:
            estado_app["ultimo_escaneo"]["id_agregado"] = nuevo_id

        guardar_progreso()
        sincronizar_boton_poner_quitar()
        actualizar_tarjeta_restantes()
        actualizar_panel_diagnostico()
        page.update()

    def quitar_comida_del_dia(id_comida):
        estado_app["comidas_hoy"] = [item for item in estado_app["comidas_hoy"] if item["id"] != id_comida]
        if estado_app["ultimo_escaneo"] and estado_app["ultimo_escaneo"].get("id_agregado") == id_comida:
            estado_app["ultimo_escaneo"]["id_agregado"] = None

        guardar_progreso()
        sincronizar_boton_poner_quitar()
        actualizar_tarjeta_restantes()
        actualizar_panel_diagnostico()
        page.update()

    def vaciar_comidas_hoy():
        estado_app["comidas_hoy"].clear()
        if estado_app["ultimo_escaneo"]:
            estado_app["ultimo_escaneo"]["id_agregado"] = None
        guardar_progreso()
        sincronizar_boton_poner_quitar()
        actualizar_tarjeta_restantes()
        actualizar_panel_diagnostico()
        page.update()

    def reconstruir_lista_comidas_hoy():
        lista_visual_comidas.controls.clear()
        if not estado_app["comidas_hoy"]:
            contenedor_registro_hoy.visible = False
            return

        contenedor_registro_hoy.visible = True
        bg_fila = "#1E293B" if estado_app["modo_oscuro"] else ft.colors.WHITE

        for item in estado_app["comidas_hoy"]:
            id_actual = item["id"]
            nombre_actual = item["nombre"]
            porcion_actual = item.get("porcion", "Mediana")
            kcal_actual = item["kcal"]
            es_sal = item.get("es_saludable", True)
            horario_actual = item.get("horario", "Almuerzo")
            efecto_actual = item.get("efecto", "Bien")
            icono_salud = "🟢" if es_sal else "🔴"

            opciones_efecto = [("😊", "Bien"), ("⚡", "Fatiga"), ("🤢", "Malestar"), ("😔", "Desmotivación")]
            botones_efecto = []
            for emoji, nombre_ef in opciones_efecto:
                activo = (efecto_actual == nombre_ef)
                botones_efecto.append(
                    ft.Container(
                        width=36,
                        height=28,
                        border_radius=6,
                        alignment=ft.alignment.center,
                        tooltip=f"Me sentí: {nombre_ef}",
                        bgcolor=ft.colors.BLUE_600 if activo else ("#334155" if estado_app["modo_oscuro"] else "#E2E8F0"),
                        on_click=lambda e, i=id_actual, ef=nombre_ef: cambiar_efecto_comida(i, ef),
                        content=ft.Text(emoji, size=14)
                    )
                )

            fila_item = ft.Container(
                padding=8,
                bgcolor=bg_fila,
                border_radius=10,
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text(f"{icono_salud} [{horario_actual}] {nombre_actual} • {porcion_actual} ({round(kcal_actual)} kcal)", size=12, weight=ft.FontWeight.BOLD, expand=True),
                                ft.IconButton(
                                    icon=ft.icons.ADD_CIRCLE_OUTLINE, icon_color=ft.colors.GREEN_400,
                                    tooltip="Poner otra porción", icon_size=19,
                                    on_click=lambda e, n=nombre_actual, k=kcal_actual, s=es_sal, h=horario_actual, p=porcion_actual: agregar_comida_al_dia(n, k, s, h, p)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.DELETE_OUTLINE, icon_color=ft.colors.RED_400,
                                    tooltip="Quitar esta comida", icon_size=19,
                                    on_click=lambda e, i=id_actual: quitar_comida_del_dia(i)
                                )
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                        ),
                        ft.Row(
                            controls=[
                                ft.Text(f"Efecto: {efecto_actual}", size=11, color=ft.colors.CYAN_300 if estado_app["modo_oscuro"] else ft.colors.BLUE_700, expand=True),
                                *botones_efecto
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                        )
                    ],
                    spacing=4
                )
            )
            lista_visual_comidas.controls.append(fila_item)

    def actualizar_tarjeta_restantes():
        reconstruir_lista_comidas_hoy()
        try:
            peso = float(input_peso.value)
            altura = float(input_altura.value)
            perfil = motor.calcular_perfil_usuario(peso, altura)
            meta_diaria = perfil["calorias_diarias_rec"]
        except ValueError:
            texto_calorias_restantes.value = "⚠️ Configura tu Peso y Altura en 'Hábitos' primero."
            tarjeta_calorias_dia.bgcolor = ft.colors.RED_700
            return

        consumidas = round(calcular_total_consumido_hoy())
        restantes = round(meta_diaria - consumidas)

        if restantes >= 0:
            tarjeta_calorias_dia.bgcolor = ft.colors.TEAL_800
            mensaje_restante = f"🔥 Calorías que te quedan hoy: {restantes:,} kcal"
        else:
            tarjeta_calorias_dia.bgcolor = ft.colors.RED_800
            mensaje_restante = f"⚠️ Excediste tu meta diaria por: {abs(restantes):,} kcal"

        texto_calorias_restantes.value = (
            f"Meta diaria: {meta_diaria:,} kcal  |  Consumido: {consumidas:,} kcal\n"
            f"{mensaje_restante}"
        )

    visor_imagen = ft.Image(width=365, height=195, fit=ft.ImageFit.COVER, border_radius=14, visible=False)

    placeholder_visor = ft.Container(
        width=365,
        height=195,
        bgcolor="#111827",
        border=ft.border.all(1, "#1F2937"),
        border_radius=14,
        alignment=ft.alignment.center,
        content=ft.Column(
            controls=[
                ft.Icon(ft.icons.IMAGE_SEARCH, size=46, color=ft.colors.TEAL_400),
                ft.Text("Toma una foto con Cámara o súbela de Galería", color=ft.colors.GREY_400, size=12)
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )
    )

    texto_estado_foto = ft.Text("", size=14, color=ft.colors.GREEN_400, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
    texto_porcion_ia = ft.Text("", size=12, color=ft.colors.CYAN_300, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER)

    input_comida = ft.TextField(
        label="Alimento detectado (o escríbelo)",
        hint_text="Ej: salchipapa, empanada, manzana...",
        width=365,
        border_radius=10,
        prefix_icon=ft.icons.RESTAURANT
    )

    texto_alimento = ft.Text(size=19, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
    texto_imc_identificar = ft.Text(size=12, text_align=ft.TextAlign.CENTER, color=ft.colors.GREY_300)

    def crear_pastilla_porcion(clave, etiqueta):
        txt = ft.Text(etiqueta, size=11, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, no_wrap=True)
        cont = ft.Container(
            width=116,
            height=36,
            border_radius=10,
            bgcolor=ft.colors.INDIGO_700,
            alignment=ft.alignment.center,
            on_click=lambda e, c=clave: cambiar_tamano_porcion(c),
            content=txt
        )
        return {"contenedor": cont, "texto": txt}

    botones_porcion = {
        "Pequeña": crear_pastilla_porcion("Pequeña", "🥣 Pequeña (0.7x)"),
        "Mediana": crear_pastilla_porcion("Mediana", "🍽️ Mediana (1.0x)"),
        "Grande": crear_pastilla_porcion("Grande", "🍛 Grande (1.45x)")
    }

    fila_botones_porcion = ft.Row(
        controls=[b["contenedor"] for b in botones_porcion.values()],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        width=365
    )

    def aplicar_colores_porcion():
        es_osc = estado_app["modo_oscuro"]
        for tam, item in botones_porcion.items():
            if tam == estado_app["porcion_seleccionada"]:
                item["contenedor"].bgcolor = ft.colors.INDIGO_600
                item["texto"].color = ft.colors.WHITE
            else:
                item["contenedor"].bgcolor = "#1E293B" if es_osc else "#E2E8F0"
                item["texto"].color = ft.colors.GREY_300 if es_osc else ft.colors.BLACK87

    def cambiar_tamano_porcion(nuevo_tamano):
        estado_app["porcion_seleccionada"] = nuevo_tamano
        aplicar_colores_porcion()
        if estado_app["alimento_actual_raw"]:
            mostrar_evaluacion(
                estado_app["alimento_actual_raw"],
                ya_en_ingles=estado_app["ya_en_ingles_actual"],
                tamano_porcion=nuevo_tamano
            )

    def crear_pastilla_horario(momento):
        txt = ft.Text(momento, size=11, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, no_wrap=True)
        cont = ft.Container(
            width=85,
            height=34,
            border_radius=10,
            bgcolor=ft.colors.TEAL_700,
            alignment=ft.alignment.center,
            on_click=lambda e, m=momento: seleccionar_horario(m),
            content=txt
        )
        return {"contenedor": cont, "texto": txt}

    botones_horario = {
        "Desayuno": crear_pastilla_horario("Desayuno"),
        "Almuerzo": crear_pastilla_horario("Almuerzo"),
        "Cena": crear_pastilla_horario("Cena"),
        "Snack": crear_pastilla_horario("Snack")
    }

    fila_botones_horario = ft.Row(
        controls=[b["contenedor"] for b in botones_horario.values()],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        width=365
    )

    def seleccionar_horario(momento):
        estado_app["horario_seleccionado"] = momento
        es_osc = estado_app["modo_oscuro"]
        for nombre_h, item in botones_horario.items():
            if nombre_h == momento:
                item["contenedor"].bgcolor = ft.colors.TEAL_700
                item["texto"].color = ft.colors.WHITE
            else:
                item["contenedor"].bgcolor = "#1E293B" if es_osc else "#E2E8F0"
                item["texto"].color = ft.colors.GREY_300 if es_osc else ft.colors.BLACK87
        page.update()

    btn_poner_quitar_actual = ft.ElevatedButton(
        text="➕ Poner en mis comidas de hoy",
        width=365,
        height=44
    )

    def accion_boton_poner_quitar(e):
        escaneo = estado_app["ultimo_escaneo"]
        if not escaneo:
            return
        if escaneo.get("id_agregado") is None:
            agregar_comida_al_dia(
                escaneo["nombre"],
                escaneo["kcal"],
                escaneo["es_saludable"],
                estado_app["horario_seleccionado"],
                estado_app["porcion_seleccionada"]
            )
        else:
            quitar_comida_del_dia(escaneo["id_agregado"])

    btn_poner_quitar_actual.on_click = accion_boton_poner_quitar

    def sincronizar_boton_poner_quitar():
        escaneo = estado_app["ultimo_escaneo"]
        if not escaneo:
            return
        kcal_num = round(escaneo["kcal"])
        porc = estado_app["porcion_seleccionada"]
        if escaneo.get("id_agregado") is None:
            btn_poner_quitar_actual.text = f"➕ Poner porción {porc} en mi día (+{kcal_num} kcal)"
            btn_poner_quitar_actual.icon = ft.icons.ADD_TASK
            btn_poner_quitar_actual.style = ft.ButtonStyle(bgcolor=ft.colors.GREEN_700, color=ft.colors.WHITE)
        else:
            btn_poner_quitar_actual.text = f"❌ Quitar de mi día (-{kcal_num} kcal)"
            btn_poner_quitar_actual.icon = ft.icons.REMOVE_CIRCLE_OUTLINE
            btn_poner_quitar_actual.style = ft.ButtonStyle(bgcolor=ft.colors.RED_700, color=ft.colors.WHITE)

    contenedor_grid_identificar = ft.Column(spacing=8)

    tarjeta_nutrientes = ft.Container(
        content=contenedor_grid_identificar,
        padding=12,
        bgcolor="#111827",
        border=ft.border.all(1, "#1F2937"),
        border_radius=14,
        width=365
    )

    indicador_salud = ft.Container(
        width=365,
        height=54,
        border_radius=12,
        bgcolor=ft.colors.GREEN_700,
        alignment=ft.alignment.center,
        padding=8,
        content=ft.Text("", size=12, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, text_align=ft.TextAlign.CENTER)
    )

    columna_resultados_comida = ft.Column(
        controls=[
            texto_alimento,
            texto_imc_identificar,
            ft.Text("Tamaño de la porción:", size=12, weight=ft.FontWeight.W_600),
            fila_botones_porcion,
            ft.Text("¿En qué momento del día lo consumes?", size=12, weight=ft.FontWeight.W_600),
            fila_botones_horario,
            btn_poner_quitar_actual,
            tarjeta_nutrientes,
            indicador_salud
        ],
        visible=False,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=8
    )

    def mostrar_evaluacion(nombre_alimento, ya_en_ingles=False, tamano_porcion=None):
        estado_app["alimento_actual_raw"] = nombre_alimento
        estado_app["ya_en_ingles_actual"] = ya_en_ingles
        porcion_usar = tamano_porcion if tamano_porcion else estado_app["porcion_seleccionada"]
        estado_app["porcion_seleccionada"] = porcion_usar
        aplicar_colores_porcion()

        try:
            peso = float(input_peso.value)
            altura = float(input_altura.value)
        except ValueError:
            texto_alimento.value = "⚠️ Revisa tu peso y altura en la sección 'Hábitos'."
            columna_resultados_comida.visible = True
            page.update()
            return

        resultado = motor.evaluar_alimento(
            nombre_alimento, peso, altura,
            ya_en_ingles=ya_en_ingles,
            tamano_porcion=porcion_usar
        )

        if "error" in resultado:
            texto_alimento.value = "❌ Alimento no encontrado"
            texto_imc_identificar.value = resultado["error"]
            btn_poner_quitar_actual.visible = False
            tarjeta_nutrientes.visible = False
            indicador_salud.bgcolor = ft.colors.GREY
            indicador_salud.content.value = "Prueba con otra foto o escribe el nombre"
        else:
            calorias_str = resultado['nutricion']['Calorías'].replace("kcal", "").strip()
            try:
                calorias_plato = float(calorias_str)
            except ValueError:
                calorias_plato = 0.0

            nombre_plato = resultado['alimento_encontrado']
            estado_app["ultimo_escaneo"] = {
                "nombre": nombre_plato,
                "kcal": calorias_plato,
                "es_saludable": resultado.get("es_saludable", True),
                "id_agregado": None
            }

            btn_poner_quitar_actual.visible = True
            sincronizar_boton_poner_quitar()

            meta_diaria = resultado['perfil_usuario']['calorias_diarias_rec']
            restantes_si_come = round(meta_diaria - (calcular_total_consumido_hoy() + calorias_plato))

            texto_alimento.value = f"🍽️ {nombre_plato} ({porcion_usar})"
            texto_imc_identificar.value = (
                f"Si comes esta porción {porcion_usar.lower()}, te quedarían hoy: {restantes_si_come:,} kcal"
            )

            contenedor_grid_identificar.controls.clear()
            contenedor_grid_identificar.controls.append(construir_grid_nutrientes(resultado["nutricion"]))
            tarjeta_nutrientes.visible = True

            if resultado['boton_color'] == "VERDE":
                indicador_salud.bgcolor = ft.colors.GREEN_600
                indicador_salud.content.value = resultado['boton_mensaje']
            else:
                indicador_salud.bgcolor = ft.colors.RED_600
                indicador_salud.content.value = resultado['boton_mensaje']

        columna_resultados_comida.visible = True
        page.update()

    def mostrar_imagen_en_visor(ruta):
        """Carga la imagen en base64 para que se visualice tanto en Android como en PC."""
        try:
            with open(ruta, "rb") as f:
                visor_imagen.src_base64 = base64.b64encode(f.read()).decode("utf-8")
            visor_imagen.src = None
        except Exception:
            visor_imagen.src = ruta
            visor_imagen.src_base64 = None
        visor_imagen.visible = True
        placeholder_visor.visible = False

    def analizar_foto_local(ruta):
        texto_estado_foto.value = "Analizando imagen y tamaño del plato..."
        texto_porcion_ia.value = ""
        page.update()

        res_ia = motor.identificar_imagen_con_ia(ruta)
        if "error" in res_ia:
            texto_estado_foto.value = res_ia["error"]
            page.update()
            return

        alimento_detectado = res_ia["alimento_en"]
        porcion_vista = res_ia.get("porcion_detectada", "Mediana")

        input_comida.value = alimento_detectado
        texto_estado_foto.value = f"Comida detectada: {alimento_detectado.capitalize()}"
        texto_porcion_ia.value = f"📏 Tamaño estimado en la imagen: Porción {porcion_vista}"
        page.update()

        mostrar_evaluacion(alimento_detectado, ya_en_ingles=True, tamano_porcion=porcion_vista)

    def archivo_seleccionado(e: ft.FilePickerResultEvent):
        detener_camara()
        if e.files and len(e.files) > 0 and e.files[0].path:
            ruta = e.files[0].path
            estado_camara["ruta_foto"] = ruta
            mostrar_imagen_en_visor(ruta)
            page.update()
            threading.Thread(target=analizar_foto_local, args=(ruta,), daemon=True).start()

    selector_archivos = ft.FilePicker(on_result=archivo_seleccionado)
    selector_camara_movil = ft.FilePicker(on_result=archivo_seleccionado)
    page.overlay.append(selector_archivos)
    page.overlay.append(selector_camara_movil)

    def abrir_galeria(e):
        selector_archivos.pick_files(
            dialog_title="Selecciona la foto de tu comida",
            file_type=ft.FilePickerFileType.IMAGE,
            allow_multiple=False
        )

    def detener_camara():
        estado_camara["activa"] = False
        if estado_camara["cap"] is not None:
            estado_camara["cap"].release()
            estado_camara["cap"] = None
        boton_camara.text = "Cámara"
        boton_camara.icon = ft.icons.CAMERA_ALT
        boton_camara.style = ft.ButtonStyle(bgcolor=ft.colors.TEAL_700, color=ft.colors.WHITE, shape=ft.RoundedRectangleBorder(radius=10))

    def transmitir_video():
        if cv2 is None:
            return

        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)
        estado_camara["cap"] = cap

        if not cap.isOpened():
            detener_camara()
            selector_camara_movil.pick_files(
                dialog_title="Tomar foto",
                file_type=ft.FilePickerFileType.VIDEO,
                allow_multiple=False
            )
            return

        placeholder_visor.visible = False
        visor_imagen.src = None
        visor_imagen.visible = True

        while estado_camara["activa"]:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue
            estado_camara["ultimo_frame"] = frame
            _, buffer = cv2.imencode('.jpg', frame)
            visor_imagen.src_base64 = base64.b64encode(buffer).decode('utf-8')
            page.update()
            time.sleep(0.03)

    def accion_camara(e):
        if cv2 is None:
            selector_camara_movil.pick_files(
                dialog_title="Tomar foto",
                file_type=ft.FilePickerFileType.VIDEO,
                allow_multiple=False
            )
            return

        if not estado_camara["activa"]:
            estado_camara["activa"] = True
            boton_camara.text = "Capturar Foto"
            boton_camara.icon = ft.icons.CAMERA
            boton_camara.style = ft.ButtonStyle(bgcolor=ft.colors.ORANGE_800, color=ft.colors.WHITE, shape=ft.RoundedRectangleBorder(radius=10))
            texto_estado_foto.value = "🔴 Cámara activa... Apunta y presiona Capturar"
            page.update()
            threading.Thread(target=transmitir_video, daemon=True).start()
        else:
            ruta_captura = None
            if "ultimo_frame" in estado_camara:
                ruta_captura = "captura_comida.jpg"
                cv2.imwrite(ruta_captura, estado_camara["ultimo_frame"])
                estado_camara["ruta_foto"] = ruta_captura
            detener_camara()
            page.update()
            if ruta_captura:
                threading.Thread(target=analizar_foto_local, args=(ruta_captura,), daemon=True).start()

    boton_camara = ft.ElevatedButton(
        text="Cámara", icon=ft.icons.CAMERA_ALT, on_click=accion_camara,
        width=176, height=44, style=ft.ButtonStyle(bgcolor=ft.colors.TEAL_700, color=ft.colors.WHITE, shape=ft.RoundedRectangleBorder(radius=10))
    )
    boton_galeria = ft.ElevatedButton(
        text="Galería", icon=ft.icons.PHOTO_LIBRARY, on_click=abrir_galeria,
        width=176, height=44, style=ft.ButtonStyle(bgcolor=ft.colors.INDIGO_600, color=ft.colors.WHITE, shape=ft.RoundedRectangleBorder(radius=10))
    )
    fila_botones_imagen = ft.Row(controls=[boton_camara, boton_galeria], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, width=365)

    def clic_boton_manual(e):
        if input_comida.value.strip():
            comida_escrita = input_comida.value.strip()
            texto_estado_foto.value = f"Comida detectada: {comida_escrita.capitalize()}"
            texto_porcion_ia.value = f"📏 Calculando para porción: {estado_app['porcion_seleccionada']}"
            mostrar_evaluacion(comida_escrita, ya_en_ingles=False, tamano_porcion=estado_app["porcion_seleccionada"])

    boton_escanear = ft.ElevatedButton(
        text="Analizar Nutrientes",
        icon=ft.icons.ANALYTICS,
        on_click=clic_boton_manual,
        width=365,
        height=44,
        style=ft.ButtonStyle(
            bgcolor=ft.colors.BLUE_700,
            color=ft.colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=12)
        )
    )

    vista_identificar = ft.Column(
        controls=[
            tarjeta_calorias_dia,
            contenedor_registro_hoy,
            placeholder_visor,
            visor_imagen,
            texto_estado_foto,
            texto_porcion_ia,
            fila_botones_imagen,
            input_comida,
            boton_escanear,
            ft.Divider(height=6),
            columna_resultados_comida
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=9,
        visible=False
    )

    # =========================================================================
    # SECCIÓN 3: "DIAGNÓSTICO"
    # =========================================================================
    subtitulo_diagnostico = ft.Text("🩺 Diagnóstico y Plan de Recuperación", size=17, weight=ft.FontWeight.BOLD)

    titulo_patron = ft.Text("", size=14, weight=ft.FontWeight.BOLD)
    texto_detalle_patron = ft.Text("", size=12)
    texto_conexion_causa = ft.Text("", size=12, italic=True)

    tarjeta_patron_alimenticio = ft.Container(
        width=365,
        padding=14,
        border_radius=14,
        bgcolor="#111827",
        border=ft.border.all(1, "#1F2937"),
        content=ft.Column(
            controls=[
                ft.Text("🔍 1. Diagnóstico de tu Patrón Alimenticio Hoy", size=13, weight=ft.FontWeight.BOLD, color=ft.colors.CYAN_400),
                titulo_patron,
                texto_detalle_patron,
                ft.Divider(height=6),
                texto_conexion_causa
            ],
            spacing=6
        )
    )

    titulo_bienestar = ft.Text("⚡ 2. Plan de Recuperación ante Síntomas", size=15, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
    subtitulo_bienestar = ft.Text("Selecciona qué malestar experimentas para recibir tu plan personalizado:", size=11, color=ft.colors.GREY_400, text_align=ft.TextAlign.CENTER)

    titulo_solucion = ft.Text("", size=14, weight=ft.FontWeight.BOLD, color=ft.colors.AMBER_300)
    texto_causa_sintoma = ft.Text("", size=12)
    texto_alimentos_sintoma = ft.Text("", size=12)
    texto_acciones_sintoma = ft.Text("", size=12)
    texto_feedback_accion = ft.Text("", size=11, weight=ft.FontWeight.BOLD, color=ft.colors.GREEN_400, text_align=ft.TextAlign.CENTER)

    def registrar_origen_identificado(e):
        estado_app["origenes_identificados"] += 1
        texto_feedback_accion.value = "✅ ¡Excelente! Registraste la causa de tu malestar (+Conciencia Nutricional)."
        guardar_progreso()
        actualizar_panel_diagnostico()
        page.update()

    def registrar_habito_modificado(e):
        estado_app["habitos_modificados"] += 1
        texto_feedback_accion.value = "🔄 ¡Muy bien! Registraste un cambio de comportamiento saludable hoy."
        guardar_progreso()
        actualizar_panel_diagnostico()
        page.update()

    btn_identifique_origen = ft.ElevatedButton(
        text="✅ Identifiqué la causa", width=162, height=38,
        on_click=registrar_origen_identificado,
        style=ft.ButtonStyle(bgcolor=ft.colors.TEAL_700, color=ft.colors.WHITE, padding=4)
    )
    btn_modifique_habito = ft.ElevatedButton(
        text="🔄 Modifiqué mi hábito", width=162, height=38,
        on_click=registrar_habito_modificado,
        style=ft.ButtonStyle(bgcolor=ft.colors.GREEN_700, color=ft.colors.WHITE, padding=4)
    )

    tarjeta_solucion_sintoma = ft.Container(
        width=365,
        padding=14,
        border_radius=14,
        bgcolor="#111827",
        border=ft.border.all(1, ft.colors.AMBER_400),
        visible=False,
        content=ft.Column(
            controls=[
                titulo_solucion,
                ft.Divider(height=6),
                ft.Text("🔍 Origen detectado en tus hábitos:", size=12, weight=ft.FontWeight.BOLD),
                texto_causa_sintoma,
                ft.Text("🥗 Alimentos recomendados:", size=12, weight=ft.FontWeight.BOLD),
                texto_alimentos_sintoma,
                ft.Text("✅ Plan de acción inmediato:", size=12, weight=ft.FontWeight.BOLD),
                texto_acciones_sintoma,
                ft.Divider(height=8),
                ft.Text("Evalúa tu regulación frente a este síntoma:", size=11, weight=ft.FontWeight.BOLD),
                ft.Row(controls=[btn_identifique_origen, btn_modifique_habito], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                texto_feedback_accion
            ],
            spacing=6
        )
    )

    def crear_pastilla_sintoma(clave, etiqueta):
        txt = ft.Text(etiqueta, size=11, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE, no_wrap=True)
        cont = ft.Container(
            width=116,
            height=38,
            border_radius=10,
            bgcolor="#1E293B",
            alignment=ft.alignment.center,
            on_click=lambda e, c=clave: mostrar_solucion_sintoma(c),
            content=txt
        )
        return {"contenedor": cont, "texto": txt}

    botones_sintomas = {
        "Fatiga": crear_pastilla_sintoma("Fatiga", "⚡ Fatiga"),
        "Malestar": crear_pastilla_sintoma("Malestar", "🤢 Malestar"),
        "Desmotivación": crear_pastilla_sintoma("Desmotivación", "😔 Desmotivación")
    }

    fila_botones_sintomas = ft.Row(
        controls=[b["contenedor"] for b in botones_sintomas.values()],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        width=365
    )

    def aplicar_colores_sintomas():
        es_osc = estado_app["modo_oscuro"]
        colores_activos = {
            "Fatiga": ft.colors.AMBER_800,
            "Malestar": ft.colors.TEAL_700,
            "Desmotivación": ft.colors.INDIGO_700
        }
        for nombre_s, item in botones_sintomas.items():
            if nombre_s == estado_app["sintoma_actual"]:
                item["contenedor"].bgcolor = colores_activos[nombre_s]
                item["texto"].color = ft.colors.WHITE
            else:
                item["contenedor"].bgcolor = "#1E293B" if es_osc else "#E2E8F0"
                item["texto"].color = ft.colors.GREY_300 if es_osc else ft.colors.BLACK87

    def mostrar_solucion_sintoma(sintoma):
        estado_app["sintoma_actual"] = sintoma
        texto_feedback_accion.value = ""
        aplicar_colores_sintomas()

        try:
            peso = float(input_peso.value)
            altura = float(input_altura.value)
            if peso <= 0 or altura <= 0:
                raise ValueError
        except ValueError:
            titulo_solucion.value = "⚠️ Ingresa primero un peso y altura válidos en 'Hábitos'."
            tarjeta_solucion_sintoma.visible = True
            page.update()
            return

        diagnostico = motor.diagnosticar_sintoma(sintoma, peso, altura, estado_app["comidas_hoy"])

        titulo_solucion.value = diagnostico["titulo"]
        texto_causa_sintoma.value = diagnostico["causa_nutricional"]
        texto_alimentos_sintoma.value = diagnostico["alimentos_recomendados"]
        texto_acciones_sintoma.value = diagnostico["solucion_inmediata"]

        if estado_app["modo_oscuro"]:
            tarjeta_solucion_sintoma.bgcolor = "#111827"
            titulo_solucion.color = ft.colors.AMBER_300
        else:
            tarjeta_solucion_sintoma.bgcolor = ft.colors.AMBER_50
            titulo_solucion.color = ft.colors.AMBER_900

        tarjeta_solucion_sintoma.visible = True
        page.update()

    texto_porcentaje_efectividad = ft.Text("0%", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.GREEN_400)
    barra_efectividad = ft.ProgressBar(width=335, value=0.0, color=ft.colors.GREEN_400, bgcolor="#334155", border_radius=8)
    texto_nivel_efectividad = ft.Text("", size=12, weight=ft.FontWeight.W_500)
    texto_metricas_efectividad = ft.Text("", size=11, color=ft.colors.GREY_400)

    tarjeta_efectividad = ft.Container(
        width=365,
        padding=14,
        border_radius=14,
        bgcolor="#111827",
        border=ft.border.all(1, ft.colors.GREEN_700),
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("📈 3. Índice de Regulación Nutricional", size=13, weight=ft.FontWeight.BOLD),
                        texto_porcentaje_efectividad
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                barra_efectividad,
                texto_nivel_efectividad,
                texto_metricas_efectividad
            ],
            spacing=6
        )
    )

    def actualizar_panel_diagnostico():
        try:
            peso = float(input_peso.value)
            altura = float(input_altura.value)
        except ValueError:
            peso, altura = 52.0, 1.70

        info_patron = motor.analizar_patron_y_conexiones(estado_app["comidas_hoy"], peso, altura)
        titulo_patron.value = info_patron["patron_titulo"]
        texto_detalle_patron.value = info_patron["patron_detalle"]
        texto_conexion_causa.value = info_patron["conexion_emocional"]

        efec = motor.calcular_efectividad_regulacion(
            estado_app["comidas_hoy"],
            estado_app["origenes_identificados"],
            estado_app["habitos_modificados"]
        )
        texto_porcentaje_efectividad.value = f"{efec['porcentaje']}%"
        barra_efectividad.value = efec["progreso_decimal"]
        texto_nivel_efectividad.value = efec["nivel"]
        texto_metricas_efectividad.value = (
            f"• Elecciones saludables hoy: {efec['comidas_saludables']}  |  "
            f"• Causas identificadas: {efec['origenes_identificados']}  |  "
            f"• Hábitos modificados: {efec['habitos_modificados']}"
        )

    vista_diagnostico = ft.Column(
        controls=[
            subtitulo_diagnostico,
            tarjeta_patron_alimenticio,
            ft.Divider(height=4),
            titulo_bienestar,
            subtitulo_bienestar,
            fila_botones_sintomas,
            tarjeta_solucion_sintoma,
            ft.Divider(height=4),
            tarjeta_efectividad
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10,
        visible=False
    )

    # =========================================================================
    # SECCIÓN 4: "AJUSTES"
    # =========================================================================
    subtitulo_config = ft.Text("⚙️ Configuración de NutriXion", size=18, weight=ft.FontWeight.BOLD)

    icono_tema = ft.Icon(ft.icons.DARK_MODE, color=ft.colors.CYAN_300, size=24)
    texto_modo_actual = ft.Text("Modo Oscuro activado", size=13, weight=ft.FontWeight.W_500)

    def alternar_tema(es_oscuro: bool):
        estado_app["modo_oscuro"] = es_oscuro
        switch_tema.value = es_oscuro
        page.theme_mode = ft.ThemeMode.DARK if es_oscuro else ft.ThemeMode.LIGHT
        page.bgcolor = "#0B0F19" if es_oscuro else "#F8FAFC"

        bg_card = "#111827" if es_oscuro else "#FFFFFF"
        borde_card = "#1F2937" if es_oscuro else "#CBD5E1"

        tarjeta_perfil_inputs.bgcolor = bg_card
        tarjeta_perfil_inputs.border = ft.border.all(1, borde_card)
        tarjeta_habitos_nutrientes.bgcolor = bg_card
        tarjeta_nutrientes.bgcolor = bg_card
        tarjeta_nutrientes.border = ft.border.all(1, borde_card)
        contenedor_registro_hoy.bgcolor = bg_card
        contenedor_registro_hoy.border = ft.border.all(1, borde_card)
        placeholder_visor.bgcolor = bg_card
        placeholder_visor.border = ft.border.all(1, borde_card)
        tarjeta_tema_config.bgcolor = bg_card
        tarjeta_tema_config.border = ft.border.all(1, borde_card)
        tarjeta_patron_alimenticio.bgcolor = bg_card
        tarjeta_patron_alimenticio.border = ft.border.all(1, borde_card)
        tarjeta_efectividad.bgcolor = bg_card

        if es_oscuro:
            icono_tema.name = ft.icons.DARK_MODE
            icono_tema.color = ft.colors.CYAN_300
            texto_modo_actual.value = "Modo Oscuro activado"
            texto_imc_identificar.color = ft.colors.GREY_300
        else:
            icono_tema.name = ft.icons.WB_SUNNY
            icono_tema.color = ft.colors.AMBER_700
            texto_modo_actual.value = "Modo Claro activado"
            texto_imc_identificar.color = ft.colors.GREY_800

        aplicar_colores_navegacion()
        aplicar_colores_periodo()
        aplicar_colores_porcion()
        aplicar_colores_sintomas()
        seleccionar_horario(estado_app["horario_seleccionado"])
        mostrar_datos_periodo()
        if estado_app["alimento_actual_raw"]:
            mostrar_evaluacion(estado_app["alimento_actual_raw"], estado_app["ya_en_ingles_actual"], estado_app["porcion_seleccionada"])
        if estado_app["sintoma_actual"]:
            mostrar_solucion_sintoma(estado_app["sintoma_actual"])
        reconstruir_lista_comidas_hoy()
        guardar_progreso()
        page.update()

    switch_tema = ft.Switch(
        value=estado_app["modo_oscuro"],
        active_color=ft.colors.GREEN_400,
        on_change=lambda e: alternar_tema(e.control.value)
    )

    btn_modo_claro = ft.ElevatedButton(
        text="☀️ Modo Claro", width=155, on_click=lambda e: alternar_tema(False),
        style=ft.ButtonStyle(bgcolor=ft.colors.AMBER_700, color=ft.colors.WHITE)
    )
    btn_modo_oscuro = ft.ElevatedButton(
        text="🌙 Modo Oscuro", width=155, on_click=lambda e: alternar_tema(True),
        style=ft.ButtonStyle(bgcolor=ft.colors.BLUE_GREY_800, color=ft.colors.WHITE)
    )

    def reiniciar_estadisticas_completas(e):
        estado_app["comidas_hoy"].clear()
        estado_app["origenes_identificados"] = 0
        estado_app["habitos_modificados"] = 0
        guardar_progreso()
        actualizar_tarjeta_restantes()
        actualizar_panel_diagnostico()
        page.update()

    tarjeta_tema_config = ft.Container(
        width=365,
        padding=16,
        border_radius=14,
        bgcolor="#111827",
        border=ft.border.all(1, "#1F2937"),
        content=ft.Column(
            controls=[
                ft.Text("1. Apariencia de la aplicación", size=14, weight=ft.FontWeight.BOLD),
                ft.Row(
                    controls=[ft.Row(controls=[icono_tema, texto_modo_actual], spacing=10), switch_tema],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                ft.Divider(height=8),
                ft.Row(controls=[btn_modo_claro, btn_modo_oscuro], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(height=12),
                ft.Text("2. Gestión de datos de evaluación", size=14, weight=ft.FontWeight.BOLD),
                ft.ElevatedButton(
                    text="🗑️ Reiniciar historial y métricas del día",
                    width=335,
                    on_click=reiniciar_estadisticas_completas,
                    style=ft.ButtonStyle(bgcolor=ft.colors.RED_700, color=ft.colors.WHITE)
                )
            ],
            spacing=12
        )
    )

    vista_configuracion = ft.Column(
        controls=[subtitulo_config, tarjeta_tema_config],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=15,
        visible=False
    )

    contenedor_principal_app.content = ft.Column(
        controls=[
            banner_encabezado,
            contenedor_barra_nav,
            vista_habitos,
            vista_identificar,
            vista_diagnostico,
            vista_configuracion
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10
    )

    actualizar_calculo_habitos()
    alternar_tema(estado_app["modo_oscuro"])
    seleccionar_periodo("Diario")
    seleccionar_horario("Almuerzo")
    aplicar_colores_porcion()
    aplicar_colores_sintomas()
    actualizar_tarjeta_restantes()
    actualizar_panel_diagnostico()

    # =========================================================================
    # SECUENCIA DE ANIMACIÓN DE APERTURA (SPLASH -> APP PRINCIPAL)
    # =========================================================================
    def ejecutar_animacion_inicio():
        time.sleep(0.15)
        logo_animado.scale = 1.0
        logo_animado.opacity = 1.0
        titulo_splash.opacity = 1.0
        subtitulo_splash.opacity = 1.0
        page.update()

        pasos = [
            (0.30, "Cargando base de salud alimenticia..."),
            (0.65, "Configurando análisis de porciones y hábitos..."),
            (0.90, "Preparando módulo de diagnóstico..."),
            (1.00, "¡Bienvenido a NutriXion!")
        ]
        for valor, mensaje in pasos:
            time.sleep(0.38)
            barra_carga_splash.value = valor
            texto_carga_splash.value = mensaje
            logo_animado.scale = 1.05 if valor < 1.0 else 1.0
            page.update()

        time.sleep(0.25)
        pantalla_splash.opacity = 0.0
        page.update()
        time.sleep(0.38)

        pantalla_splash.visible = False
        page.scroll = ft.ScrollMode.AUTO
        contenedor_principal_app.visible = True
        page.update()

    threading.Thread(target=ejecutar_animacion_inicio, daemon=True).start()


if __name__ == "__main__":
    ft.app(target=main)