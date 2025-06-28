import serial
import serial.tools.list_ports
import threading
import dash
from dash import html, dcc
from dash.dependencies import Output, Input
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import numpy as np
import time
import sys
from datetime import datetime, timedelta
from dash import dash_table

# Detectar puerto Arduino
def detectar_puerto_arduino():
    puertos = serial.tools.list_ports.comports()
    for puerto in puertos:
        if "Arduino" in puerto.description or "CH340" in puerto.description:
            return puerto.device
    return None

puerto = detectar_puerto_arduino()
if puerto is None:
    print("❌ Arduino no encontrado. Conéctalo al USB.")
    sys.exit()

try:
    arduino = serial.Serial(puerto, 9600, timeout=1)
    print(f"✅ Conectado al Arduino en {puerto}")
except serial.SerialException as e:
    print(f"❌ No se pudo abrir el puerto {puerto}:\n{e}")
    sys.exit()

humedad_valor = 0  # Valor inicial de humedad
nivel_riego_valor = 0  # Valor inicial de porcentaje de agua
temperatura_valor = 0  # Valor inicial de temperatura
is_connected = True  # Estado de conexión
target_humedad = 0  # Valor objetivo para transición suave
target_agua = 0     # Valor objetivo para transición suave
target_temperatura = 0  # Valor objetivo para transición suave
data_history = []   # Lista para almacenar datos: [timestamp, humedad, agua, temperatura]

def check_and_reconnect():
    global arduino, is_connected, puerto
    while True:
        if not is_connected:
            new_puerto = detectar_puerto_arduino()
            if new_puerto and new_puerto == puerto:
                try:
                    arduino.close()
                    arduino = serial.Serial(puerto, 9600, timeout=1)
                    print(f"✅ Reconectado al Arduino en {puerto}")
                    is_connected = True
                except serial.SerialException as e:
                    print(f"❌ Error al reconectar: {e}")
        time.sleep(2)  # Verificar cada 2 segundos

def leer_serial():
    global humedad_valor, nivel_riego_valor, temperatura_valor, is_connected, target_humedad, target_agua, target_temperatura, data_history
    time.sleep(2)  # Esperar para que el Arduino se estabilice
    while True:
        try:
            if arduino.in_waiting > 0:
                data = arduino.readline().decode('utf-8').strip()
                # Verificar formato "Humedad: X% | Temperatura: Y°C"
                if "Humedad" in data and "Temperatura" in data:
                    try:
                        # Extraer humedad y temperatura
                        humedad_str = data.split("|")[0].split(":")[1].strip().replace("%", "")
                        temperatura_str = data.split("|")[1].split(":")[1].strip().replace("°C", "")
                        target_humedad = int(humedad_str)
                        target_agua = target_humedad  # Mantener lógica original
                        target_temperatura = float(temperatura_str)
                        is_connected = True
                        # Almacenar datos con timestamp
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        data_history.append([timestamp, target_humedad, target_agua, target_temperatura])
                        # Mantener solo las últimas 10 entradas
                        if len(data_history) > 10:
                            data_history.pop(0)
                    except (ValueError, IndexError) as e:
                        print(f"Dato inválido recibido: {data}, Error: {e}")
                else:
                    print(f"Dato inválido recibido: {data}")
            time.sleep(0.1)  # Pequeña espera para no sobrecargar la CPU
        except (serial.SerialException, ValueError) as e:
            print(f"Error en lectura serial: {e}")
            is_connected = False
            target_humedad = 0
            target_agua = 0
            target_temperatura = 0
            time.sleep(1)  # Esperar antes de reintentar

threading.Thread(target=leer_serial, daemon=True).start()
threading.Thread(target=check_and_reconnect, daemon=True).start()

# Función para obtener datos de la última hora
def obtener_valores_ultima_hora(data_history):
    ahora = datetime.now()
    una_hora_atras = ahora - timedelta(hours=1)
    valores_ultima_hora = []

    for row in data_history:
        timestamp_str = row[0]
        try:
            timestamp = datetime.strptime(timestamp_str, "%H:%M:%S")
            timestamp = timestamp.replace(year=ahora.year, month=ahora.month, day=ahora.day)
        except:
            continue

        if timestamp >= una_hora_atras:
            valores_ultima_hora.append(row)

    return valores_ultima_hora

# Estilos y scripts externos
external_stylesheets = [
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css",
]
external_scripts = [
    "https://code.jquery.com/jquery-3.6.0.min.js",
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"
]

app = dash.Dash(__name__, external_stylesheets=external_stylesheets, external_scripts=external_scripts)

# Layout del dashboard
app.layout = html.Div(className="hold-transition sidebar-mini layout-fixed", children=[
    html.Div(className="wrapper", children=[
        html.Div(className="content-wrapper", children=[
            html.Div(className="content-header", children=[
                html.Div(className="container-fluid", children=[
                    html.H1("AgroDuino 🌱", className="m-0"),
                    dbc.Alert(id="notification-alert", is_open=False, duration=5000, color="primary", dismissable=True,
                              className="notification-alert")
                ])
            ]),
            html.Section(className="content", children=[
                html.Div(className="container-fluid", children=[
                    # Fila de gauges
                    html.Div(className="row", children=[
                        html.Div(className="col-md-4", children=[
                            html.Div(className="card border-left-primary shadow h-100 py-2", children=[
                                html.Div(className="card-body", children=[
                                    html.Div(className="row no-gutters align-items-center", children=[
                                        html.Div(className="col mr-2", children=[
                                            html.Div("Humedad del Suelo (%)", className="text-xs font-weight-bold text-primary text-uppercase mb-1 text-center"),
                                            html.Div(id="humedad-gauge", className="h5 mb-0 font-weight-bold text-gray-800")
                                        ])
                                    ])
                                ])
                            ])
                        ]),
                        html.Div(className="col-md-4", children=[
                            html.Div(className="card border-left-info shadow h-100 py-2", children=[
                                html.Div(className="card-body", children=[
                                    html.Div(className="row no-gutters align-items-center", children=[
                                        html.Div(className="col mr-2", children=[
                                            html.Div("Porcentaje de Agua (%)", className="text-xs font-weight-bold text-info text-uppercase mb-1 text-center"),
                                            html.Div(id="agua-gauge", className="h5 mb-0 font-weight-bold text-gray-800")
                                        ])
                                    ])
                                ])
                            ])
                        ]),
                        html.Div(className="col-md-4", children=[
                            html.Div(className="card border-left-info shadow h-100 py-2", children=[
                                html.Div(className="card-body", children=[
                                    html.Div(className="row no-gutters align-items-center", children=[
                                        html.Div(className="col mr-2", children=[
                                            html.Div("Temperatura (°C)", className="text-xs font-weight-bold text-info text-uppercase mb-1 text-center"),
                                            html.Div(id="temperatura-gauge", className="h5 mb-0 font-weight-bold text-gray-800")
                                        ])
                                    ])
                                ])
                            ])
                        ])
                    ]),
                    # Fila de Tasks y Pending Requests
                    html.Div(className="row mt-4", children=[
                        html.Div(className="col-md-6", children=[
                            html.Div(className="card border-left-success shadow h-100 py-2", children=[
                                html.Div(className="card-body", children=[
                                    html.Div(className="row no-gutters align-items-center", children=[
                                        html.Div(className="col mr-2", children=[
                                            html.Div("Tasks", className="text-xs font-weight-bold text-success text-uppercase mb-1 text-center"),
                                            html.Div(id="tasks-text", className="h5 mb-0 font-weight-bold text-gray-800"),
                                            html.Div(className="progress", children=[
                                                html.Div(id="tasks-bar-style", className="progress-bar bg-success", style={"width": "0%"})
                                            ])
                                        ])
                                    ])
                                ])
                            ])
                        ]),
                        html.Div(className="col-md-6", children=[
                            html.Div(className="card border-left-warning shadow h-100 py-2", children=[
                                html.Div(className="card-body", children=[
                                    html.Div(className="row no-gutters align-items-center", children=[
                                        html.Div(className="col mr-2", children=[
                                            html.Div("Pending Requests", className="text-xs font-weight-bold text-warning text-uppercase mb-1 text-center"),
                                            html.Div(id="pending-text", className="h5 mb-0 font-weight-bold text-gray-800"),
                                            html.Div(className="progress", children=[
                                                html.Div(id="pending-bar-style", className="progress-bar bg-warning", style={"width": "0%"})
                                            ])
                                        ])
                                    ])
                                ])
                            ])
                        ])
                    ]),
                    # Fila de tabla y gráficos
                    html.Div(className="row mt-4 text-center", children=[
                        html.Div(className="col-md-4", children=[
                            html.Div(className="card", children=[
                                html.Div(className="card-header", children=[
                                    html.H3("Historial de Datos", className="card-title")
                                ]),
                                html.Div(className="card-body", children=[
                                    dash_table.DataTable(
                                        id='data-table',
                                        columns=[
                                            {"name": "Hora", "id": "timestamp"},
                                            {"name": "Humedad (%)", "id": "humedad"},
                                            # {"name": "Agua (%)", "id": "agua"},
                                            {"name": "Temperatura (°C)", "id": "temperatura"}
                                        ],
                                        style_table={'overflowX': 'auto'},
                                        style_cell={'textAlign': 'center', 'padding': '8px', 'border': '1px solid #dee2e6', 'backgroundColor': 'white'},
                                        style_header={'backgroundColor': '#007bff', 'color': 'white', 'fontWeight': 'bold', 'border': 'none'},
                                        style_data_conditional=[
                                            {
                                                'if': {'state': 'active'},
                                                'backgroundColor': '#f8f9fa',
                                                'color': '#6c757d'
                                            }
                                        ]
                                    )
                                ])
                            ])
                        ]),
                        html.Div(className="col-md-4 graph-card text-center", children=[
                            html.Div(className="card", children=[
                                html.Div(className="card-header", children=[
                                    html.H3("Tendencia de Humedad", className="card-title")
                                ]),
                                html.Div(className="card-body", children=[
                                    dcc.Graph(id='humidity-bar-graph')
                                ])
                            ])
                        ]),
                        html.Div(className="col-md-4 graph-card text-center", children=[
                            html.Div(className="card", children=[
                                html.Div(className="card-header", children=[
                                    html.H3("Tendencia de Temperatura", className="card-title")
                                ]),
                                html.Div(className="card-body", children=[
                                    dcc.Graph(id='temperature-line-graph')
                                ])
                            ])
                        ])
                    ])
                ])
            ])
        ]),
        html.Footer("© 2025 AgroDuino.", className="main-footer")
    ]),
    dcc.Interval(id='interval-component', interval=100, n_intervals=0)
])

# Función para crear gauge semicircular
def semicircular_gauge(current_value, target_value, colors, title, suffix="%", is_active=True, max_value=100):
    if not is_active:
        current_value = 0
        colors = {'bar': '#cccccc', 'background': '#e0e0e0'}
    elif abs(current_value - target_value) > 0:
        current_value += np.sign(target_value - current_value) * min(5, abs(target_value - current_value))
    val = np.clip(current_value, 0, max_value)

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val,
        gauge={
            'axis': {'range': [0, max_value], 'tickwidth': 1},
            'bar': {'color': colors['bar']},
            'bgcolor': colors['background'],
            'borderwidth': 2,
            'bordercolor': "#fff",
            'steps': [{'range': [0, max_value], 'color': colors['background']}],
            'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': max_value}
        },
        number={'suffix': suffix, 'font': {'size': 40, 'color': colors['bar']}},
        domain={'x': [0, 1], 'y': [0, 1]}
    ))

    fig.update_layout(
        margin=dict(t=20, b=0, l=0, r=0),
        height=150,
        paper_bgcolor='rgba(0,0,0,0)',
        font={'color': "white" if is_active else "#888"},
        annotations=[dict(text=title, x=0.5, y=1.1, showarrow=False,
                          font=dict(size=12, color='black' if is_active else '#888'), xanchor='center')]
    )
    return fig, current_value

# Callback para actualizar dashboard
@app.callback(
    [Output('humedad-gauge', 'children'),
     Output('agua-gauge', 'children'),
     Output('temperatura-gauge', 'children'),
     Output('notification-alert', 'children'),
     Output('notification-alert', 'is_open'),
     Output('notification-alert', 'color'),
     Output('data-table', 'data'),
     Output('data-table', 'style_data_conditional'),
     Output('humidity-bar-graph', 'figure'),
     Output('temperature-line-graph', 'figure'),
     Output('tasks-text', 'children'),
     Output('tasks-bar-style', 'style'),
     Output('pending-text', 'children'),
     Output('pending-bar-style', 'style')],
    Input('interval-component', 'n_intervals')
)
def update_dashboard(n):
    global humedad_valor, nivel_riego_valor, temperatura_valor, is_connected, target_humedad, target_agua, target_temperatura, data_history

    # Actualizar valores con transición suave
    fig_hum, humedad_valor = semicircular_gauge(humedad_valor, target_humedad,
                                              colors={'bar': '#4e73df', 'background': '#e0e0e0'},
                                              title="Humedad", is_active=is_connected)
    fig_agua, nivel_riego_valor = semicircular_gauge(nivel_riego_valor, target_agua,
                                                   colors={'bar': '#36b9cc', 'background': '#e0e0e0'},
                                                   title="Agua", is_active=is_connected)
    fig_temp, temperatura_valor = semicircular_gauge(temperatura_valor, target_temperatura,
                                                   colors={'bar': '#e74a3b', 'background': '#e0e0e0'},
                                                   title="Temperatura", suffix="°C", is_active=is_connected, max_value=50)

    # Lógica de notificaciones
    if not is_connected:
        notification = html.Div("⚠ Arduino no está conectado. Conéctalo para ver datos.", className="mb-0")
        is_open = True
        color = "warning"
    else:
        # Condiciones para humedad
        humedad_message = ""
        humedad_color = "success"
        if target_humedad < 30:
            humedad_message = "⚠ Suelo muy seco, ¡necesita riego!"
            humedad_color = "danger"
        elif target_humedad > 80:
            humedad_message = "✅ Suelo muy húmedo, no riegue."
            humedad_color = "info"
        else:
            humedad_message = "🌱 Suelo en buen estado."

        # Condiciones para temperatura
        temperatura_message = ""
        temperatura_color = "success"
        if target_temperatura < 20:
            temperatura_message = "⚠ Temperatura demasiado baja, riesgo para las plantas."
            temperatura_color = "danger"
        elif target_temperatura > 30:
            temperatura_message = "⚠ Temperatura demasiado alta, riesgo para las plantas."
            temperatura_color = "danger"
        else:
            temperatura_message = "✅ Temperatura óptima."

        # Combinar mensajes y determinar color
        if humedad_color == "danger" or temperatura_color == "danger":
            color = "danger"
            if humedad_message and temperatura_message:
                notification = html.Div(f"{humedad_message} | {temperatura_message}", className="mb-0")
            else:
                notification = html.Div(humedad_message or temperatura_message, className="mb-0")
        elif humedad_color == "info" or temperatura_color == "info":
            color = "info"
            if humedad_message and temperatura_message:
                notification = html.Div(f"{humedad_message} | {temperatura_message}", className="mb-0")
            else:
                notification = html.Div(humedad_message or temperatura_message, className="mb-0")
        else:
            color = "success"
            notification = html.Div(f"{humedad_message} | {temperatura_message}", className="mb-0")
        is_open = True

    # Preparar datos de la tabla
    table_data = [{"timestamp": row[0], "humedad": row[1], "agua": row[2], "temperatura": row[3]} for row in data_history]

    # Estilo condicional para la tabla
    table_style = [
        {
            'if': {'state': 'active'},
            'backgroundColor': '#f8f9fa',
            'color': '#6c757d'
        }
    ] if not is_connected else []

    # Gráfico de barras para humedad
    bar_fig = go.Figure()
    if is_connected:
        timestamps = [row[0] for row in data_history]
        humidities = [row[1] for row in data_history]
        colors = ['red' if h < 30 or h > 80 else 'green' for h in humidities]
        bar_fig.add_trace(go.Bar(x=timestamps, y=humidities, marker_color=colors))
        bar_fig.update_layout(
            title="Tendencia de Humedad",
            xaxis_title="Hora",
            yaxis_title="Humedad (%)",
            yaxis_range=[0, 100],
            height=300,
            margin=dict(t=40, b=40, l=40, r=40)
        )
    else:
        bar_fig.add_annotation(
            text="Desconectado",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=20, color="#888"),
            opacity=0.7
        )
        bar_fig.update_layout(
            height=300,
            margin=dict(t=40, b=40, l=40, r=40),
            plot_bgcolor='rgba(240,240,240,0.5)',
            paper_bgcolor='rgba(240,240,240,0.5)'
        )

    # Gráfico de líneas para temperatura
    line_fig = go.Figure()
    if is_connected and data_history:
        timestamps = [row[0] for row in data_history]
        temperatures = [row[3] for row in data_history]
        colors = ['red' if t < 15 or t > 35 else 'blue' for t in temperatures]
        line_fig.add_trace(go.Scatter(
            x=timestamps,
            y=temperatures,
            mode='lines+markers',
            name='Temperatura (°C)',
            line=dict(color='blue', width=2, shape='spline'),
            marker=dict(size=8, color=colors)
        ))
        line_fig.update_layout(
            title="Tendencia de Temperatura",
            xaxis_title="Hora",
            yaxis_title="Temperatura (°C)",
            yaxis_range=[0, 50],
            height=300,
            margin=dict(t=40, b=40, l=40, r=40)
        )
    else:
        line_fig.add_annotation(
            text="Desconectado",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=20, color="#888"),
            opacity=0.7
        )
        line_fig.update_layout(
            height=300,
            margin=dict(t=40, b=40, l=40, r=40),
            plot_bgcolor='rgba(240,240,240,0.5)',
            paper_bgcolor='rgba(240,240,240,0.5)'
        )

    valores_en_ultima_hora = obtener_valores_ultima_hora(data_history)

    if is_connected:
        # Tasks: estimación de tiempo de riego en minutos
        if target_humedad < 30:
            tiempo_riego = (30 - target_humedad) * 2  # 2 minutos por cada % bajo
        else:
            tiempo_riego = 0
        tasks_text = f"Tiempo riego estimado: {tiempo_riego:.0f} min" if tiempo_riego > 0 else "Riego no necesario"
        tasks_bar_width = f"{min(tiempo_riego * 3, 100)}%"  # max 100%

        # Pending Requests: lecturas óptimas (30-80%)
        conteo_optimo = sum(1 for v in valores_en_ultima_hora if 30 <= v[1] <= 80)
        pending_text = f"Lecturas óptimas: {conteo_optimo}"
        pending_bar_width = f"{min(conteo_optimo * 10, 100)}%"
    else:
        tasks_text = "Desconectado"
        tasks_bar_width = "0%"
        pending_text = "Desconectado"
        pending_bar_width = "0%"

    return (
        dcc.Graph(figure=fig_hum),
        dcc.Graph(figure=fig_agua),
        dcc.Graph(figure=fig_temp),
        notification,
        is_open,
        color,
        table_data,
        table_style,
        bar_fig,
        line_fig,
        tasks_text,
        {"width": tasks_bar_width, "backgroundColor": "#1cc88a"},
        pending_text,
        {"width": pending_bar_width, "backgroundColor": "#f6c23e"}
    )

if __name__ == '__main__':
    # app.run(debug=True, use_reloader=False)
    app.run(host='0.0.0.0', port=8050, debug=True, use_reloader=False) #PARA VER EN TÚ CELULAR CON LA MISMA RED