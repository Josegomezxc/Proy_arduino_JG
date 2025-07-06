import serial
import serial.tools.list_ports
import threading
import dash
from dash import html, dcc
from dash.dependencies import Output, Input, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import numpy as np
import time
import sys
from datetime import datetime, timedelta
from dash import dash_table
from collections import deque

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

# Variables globales
humedad_valor = 0
nivel_riego_valor = 0
temperatura_valor = 0
humedad_ambiente_valor = 0
is_connected = True
target_humedad = 0
target_agua = 0
target_temperatura = 0
target_humedad_ambiente = 0
data_history = deque(maxlen=10)

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
        time.sleep(2)

def leer_serial():
    global humedad_valor, nivel_riego_valor, temperatura_valor, humedad_ambiente_valor, is_connected, target_humedad, target_agua, target_temperatura, target_humedad_ambiente, data_history
    time.sleep(2)
    while True:
        try:
            if arduino.in_waiting > 0:
                data = arduino.readline().decode('utf-8').strip()
                if "Humedad Suelo" in data and "Temperatura" in data and "Humedad Ambiente" in data:
                    try:
                        humedad_str = data.split("|")[0].split(":")[1].strip().replace("%", "")
                        temperatura_str = data.split("|")[1].split(":")[1].strip().replace("°C", "")
                        humedad_ambiente_str = data.split("|")[2].split(":")[1].strip().replace("%", "")
                        target_humedad = int(humedad_str)
                        target_agua = target_humedad
                        target_temperatura = float(temperatura_str)
                        target_humedad_ambiente = float(humedad_ambiente_str)
                        is_connected = True
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        data_history.append([timestamp, target_humedad, target_agua, target_temperatura, target_humedad_ambiente])
                    except (ValueError, IndexError) as e:
                        print(f"Dato inválido: {data}, Error: {e}")
            time.sleep(0.05)
        except (serial.SerialException, ValueError) as e:
            print(f"Error en lectura serial: {e}")
            is_connected = False
            target_humedad = 0
            target_agua = 0
            target_temperatura = 0
            target_humedad_ambiente = 0
            time.sleep(1)

threading.Thread(target=leer_serial, daemon=True).start()
threading.Thread(target=check_and_reconnect, daemon=True).start()

def obtener_valores_ultima_hora(data_history):
    ahora = datetime.now()
    una_hora_atras = ahora - timedelta(hours=1)
    valores_ultima_hora = []
    for row in data_history:
        timestamp_str = row[0]
        try:
            timestamp = datetime.strptime(timestamp_str, "%H:%M:%S")
            timestamp = timestamp.replace(year=ahora.year, month=ahora.month, day=ahora.day)
            if timestamp >= una_hora_atras:
                valores_ultima_hora.append(row)
        except ValueError:
            continue
    return valores_ultima_hora

# Estilos para tema oscuro
external_stylesheets = [
    dbc.themes.DARKLY,
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css",
]
external_scripts = [
    "https://code.jquery.com/jquery-3.6.0.min.js",
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"
]

app = dash.Dash(__name__, external_stylesheets=external_stylesheets, external_scripts=external_scripts)

app.layout = html.Div(id="main-container", className="hold-transition sidebar-mini layout-fixed", style={'backgroundColor': '#1e2b33'}, children=[
    html.Div(className="wrapper", children=[
        html.Div(className="content-wrapper", children=[
            html.Div(className="content-header", children=[
                html.Div(className="container-fluid", children=[
                    html.Div(className="d-flex justify-content-between align-items-center", children=[
                        html.H1("AgroDuino 🌱", className="m-0 text-center")
                    ]),
                    html.Div(className="mt-2", children=[
                        dbc.Alert(id="connection-alert", is_open=False, duration=5000, color="warning", dismissable=True, className="notification-alert mb-2"),
                        dbc.Alert(id="humedad-alert", is_open=False, duration=5000, color="primary", dismissable=True, className="notification-alert mb-2"),
                        dbc.Alert(id="temperatura-alert", is_open=False, duration=5000, color="primary", dismissable=True, className="notification-alert mb-2"),
                        dbc.Alert(id="humedad-ambiente-alert", is_open=False, duration=5000, color="primary", dismissable=True, className="notification-alert mb-2")
                    ])
                ])
            ]),
            html.Section(className="content", children=[
                html.Div(className="container-fluid", children=[
                    html.Div(className="row", children=[
                        html.Div(className="col-md-3", children=[
                            html.Div(className="card border-left-primary shadow h-100 py-2", children=[
                                html.Div(className="card-body", children=[
                                    html.Div(className="row no-gutters align-items-center", children=[
                                        html.Div(className="col mr-2", children=[
                                            html.Div("Humedad del Suelo (%)", className="text-xs font-weight-bold text-info text-uppercase mb-1 text-center"),
                                            html.Div(html.I(className="fas fa-tint fa-2x", style={'color': '#4e73df'}), className="text-center mb-2"),
                                            html.Div(id="humedad-gauge")
                                        ])
                                    ])
                                ])
                            ])
                        ]),
                        html.Div(className="col-md-3", children=[
                            html.Div(className="card border-left-info shadow h-100 py-2", children=[
                                html.Div(className="card-body", children=[
                                    html.Div(className="row no-gutters align-items-center", children=[
                                        html.Div(className="col mr-2", children=[
                                            html.Div("Porcentaje de Agua (%)", className="text-xs font-weight-bold text-info text-uppercase mb-1 text-center"),
                                            html.Div(html.I(className="fas fa-water fa-2x", style={'color': '#36b9cc'}), className="text-center mb-2"),
                                            html.Div(id="agua-gauge")
                                        ])
                                    ])
                                ])
                            ])
                        ]),
                        html.Div(className="col-md-3", children=[
                            html.Div(className="card border-left-info shadow h-100 py-2", children=[
                                html.Div(className="card-body", children=[
                                    html.Div(className="row no-gutters align-items-center", children=[
                                        html.Div(className="col mr-2", children=[
                                            html.Div("Temperatura (°C)", className="text-xs font-weight-bold text-danger text-uppercase mb-1 text-center"),
                                            html.Div(html.I(className="fas fa-thermometer-half fa-2x", style={'color': '#e74a3b'}), className="text-center mb-2"),
                                            html.Div(id="temperatura-gauge")
                                        ])
                                    ])
                                ])
                            ])
                        ]),
                        html.Div(className="col-md-3", children=[
                            html.Div(className="card border-left-success shadow h-100 py-2", children=[
                                html.Div(className="card-body", children=[
                                    html.Div(className="row no-gutters align-items-center", children=[
                                        html.Div(className="col mr-2", children=[
                                            html.Div("Humedad Ambiental (%)", className="text-xs font-weight-bold text-success text-uppercase mb-1 text-center"),
                                            html.Div(html.I(className="fas fa-cloud fa-2x", style={'color': '#1cc88a'}), className="text-center mb-2"),
                                            html.Div(id="humedad-ambiente-gauge")
                                        ])
                                    ])
                                ])
                            ])
                        ])
                    ]),
                    html.Div(className="row mt-4", children=[
                        html.Div(className="col-md-6", children=[
                            html.Div(className="card border-left-success shadow h-100 py-2", children=[
                                html.Div(className="card-body", children=[
                                    html.Div(className="row no-gutters align-items-center", children=[
                                        html.Div(className="col mr-2", children=[
                                            html.Div(children=[
                                                html.I(className="fas fa-tasks mr-2"),
                                                " Gestión de Riego"
                                            ], className="text-xs font-weight-bold text-success text-uppercase mb-1 text-center"),
                                            html.Div(id="tasks-text", className="h5 mb-0 font-weight-bold"),
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
                                            html.Div(children=[
                                                html.I(className="fas fa-hourglass-half mr-2"),
                                                " Evaluación de Condiciones"
                                            ], className="text-xs font-weight-bold text-warning text-uppercase mb-1 text-center"),
                                            html.Div(id="pending-text", className="h5 mb-0 font-weight-bold"),
                                            html.Div(className="progress", children=[
                                                html.Div(id="pending-bar-style", className="progress-bar bg-warning", style={"width": "0%"})
                                            ])
                                        ])
                                    ])
                                ])
                            ])
                        ])
                    ]),
                    html.Div(className="row mt-4 text-center", children=[
                        html.Div(className="col-md-3", children=[
                            html.Div(className="card", children=[
                                html.Div(className="card-header", children=[
                                    html.H3("Historial de Datos", className="card-title")
                                ]),
                                html.Div(className="card-body", children=[
                                    dash_table.DataTable(
                                        id='data-table',
                                        columns=[
                                            {"name": "Hora", "id": "timestamp"},
                                            {"name": "Humedad Suelo (%)", "id": "humedad"},
                                            {"name": "Temperatura (°C)", "id": "temperatura"},
                                            {"name": "Humedad Ambiental (%)", "id": "humedad_ambiente"}
                                        ],
                                        style_table={'overflowX': 'auto', 'backgroundColor': '#1e2b33'},
                                        style_cell={'textAlign': 'center', 'padding': '8px', 'border': '1px solid #4b5e6b', 'backgroundColor': '#2c3b41', 'color': '#e0e0e0'},
                                        style_header={'backgroundColor': '#007bff', 'color': 'white', 'fontWeight': 'bold', 'border': 'none'},
                                        style_data_conditional=[
                                            {
                                                'if': {'state': 'active'},
                                                'backgroundColor': '#495057',
                                                'color': '#e0e0e0'
                                            }
                                        ]
                                    )
                                ])
                            ])
                        ]),
                        html.Div(className="col-md-3 graph-card text-center", children=[
                            html.Div(className="card", children=[
                                html.Div(className="card-header", children=[
                                    html.H3(children=[
                                        "Tendencia de Humedad ",
                                        html.I(className="fas fa-tint ml-2", style={'color': '#4e73df'})
                                    ], className="card-title d-flex align-items-center justify-content-center", style={'color': '#4e73df'})
                                ]),
                                html.Div(className="card-body", children=[
                                    dcc.Graph(id='humidity-bar-graph')
                                ])
                            ])
                        ]),
                        html.Div(className="col-md-3 graph-card text-center", children=[
                            html.Div(className="card", children=[
                                html.Div(className="card-header", children=[
                                    html.H3(children=[
                                        "Tendencia de Temperatura ",
                                        html.I(className="fas fa-thermometer-half ml-2", style={'color': '#e74a3b'})
                                    ], className="card-title d-flex align-items-center justify-content-center", style={'color': '#e74a3b'})
                                ]),
                                html.Div(className="card-body", children=[
                                    dcc.Graph(id='temperature-line-graph')
                                ])
                            ])
                        ]),
                        html.Div(className="col-md-3 graph-card text-center", children=[
                            html.Div(className="card", children=[
                                html.Div(className="card-header", children=[
                                    html.H3(children=[
                                        "Humedad Ambiental",
                                        html.I(className="fas fa-cloud ml-2", style={'color': '#1cc88a'})
                                    ], className="card-title d-flex align-items-center justify-content-center", style={'color': '#1cc88a'})
                                ]),
                                html.Div(className="card-body", children=[
                                    dcc.Graph(id='humedad-ambiente-bar-graph')
                                ])
                            ])
                        ])
                    ])
                ])
            ])
        ]),
        html.Footer("© 2025 AgroDuino.", className="main-footer")
    ]),
    dcc.Interval(id='interval-component', interval=1500, n_intervals=0)
])

def semicircular_gauge(current_value, target_value, colors, title, suffix="%", is_active=True, max_value=100):
    if not is_active:
        current_value = 0
        colors = {'bar': '#cccccc', 'background': '#4b5e6b'}
    elif abs(current_value - target_value) > 0:
        current_value += np.sign(target_value - current_value) * min(15, abs(target_value - current_value))
    val = np.clip(current_value, 0, max_value)

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val,
        gauge={
            'axis': {'range': [0, max_value], 'tickwidth': 1, 'tickcolor': '#e0e0e0'},
            'bar': {'color': colors['bar']},
            'bgcolor': colors['background'],
            'borderwidth': 2,
            'bordercolor': '#4b5e6b',
            'steps': [{'range': [0, max_value], 'color': colors['background']}],
            'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': max_value}
        },
        number={'suffix': suffix, 'font': {'size': 40, 'color': colors['bar']}},
        domain={'x': [0, 1], 'y': [0, 1]}
    ))

    fig.update_layout(
        margin=dict(t=20, b=0, l=0, r=0),
        height=150,
        paper_bgcolor='#1e2b33',
        plot_bgcolor='#1e2b33',
        font={'color': '#e0e0e0'},
        annotations=[dict(text=title, x=0.5, y=1.1, showarrow=False,
                          font=dict(size=12, color='#e0e0e0'), xanchor='center')]
    )
    return fig, current_value

# Callback para gauges
@app.callback(
    [Output('humedad-gauge', 'children'),
     Output('agua-gauge', 'children'),
     Output('temperatura-gauge', 'children'),
     Output('humedad-ambiente-gauge', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_gauges(n):
    global humedad_valor, nivel_riego_valor, temperatura_valor, humedad_ambiente_valor, is_connected, target_humedad, target_agua, target_temperatura, target_humedad_ambiente
    fig_hum, humedad_valor = semicircular_gauge(humedad_valor, target_humedad,
                                              colors={'bar': '#4e73df', 'background': '#4b5e6b'},
                                              title="Humedad Suelo", is_active=is_connected)
    fig_agua, nivel_riego_valor = semicircular_gauge(nivel_riego_valor, target_agua,
                                                   colors={'bar': '#36b9cc', 'background': '#4b5e6b'},
                                                   title="Agua", is_active=is_connected)
    fig_temp, temperatura_valor = semicircular_gauge(temperatura_valor, target_temperatura,
                                                   colors={'bar': '#e74a3b', 'background': '#4b5e6b'},
                                                   title="Temperatura", suffix="°C", is_active=is_connected, max_value=50)
    fig_hum_amb, humedad_ambiente_valor = semicircular_gauge(humedad_ambiente_valor, target_humedad_ambiente,
                                                            colors={'bar': '#1cc88a', 'background': '#4b5e6b'},
                                                            title="Humedad Ambiental", is_active=is_connected)
    return dcc.Graph(figure=fig_hum), dcc.Graph(figure=fig_agua), dcc.Graph(figure=fig_temp), dcc.Graph(figure=fig_hum_amb)

# Callback para notificaciones
@app.callback(
    [Output('connection-alert', 'children'),
     Output('connection-alert', 'is_open'),
     Output('connection-alert', 'color'),
     Output('humedad-alert', 'children'),
     Output('humedad-alert', 'is_open'),
     Output('humedad-alert', 'color'),
     Output('temperatura-alert', 'children'),
     Output('temperatura-alert', 'is_open'),
     Output('temperatura-alert', 'color'),
     Output('humedad-ambiente-alert', 'children'),
     Output('humedad-ambiente-alert', 'is_open'),
     Output('humedad-ambiente-alert', 'color')],
    Input('interval-component', 'n_intervals')
)
def update_notifications(n):
    global is_connected, target_humedad, target_temperatura, target_humedad_ambiente
    if not is_connected:
        return (
            html.Div("⚠ Arduino no está conectado. Conéctalo para ver datos.", className="mb-0"), True, "warning",
            html.Div(""), False, "success",  # Ocultar alerta de humedad
            html.Div(""), False, "success",  # Ocultar alerta de temperatura
            html.Div(""), False, "success"   # Ocultar alerta de humedad ambiental
        )
    
    # Notificación para humedad del suelo
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

    # Notificación para temperatura
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

    # Notificación para humedad ambiental
    humedad_ambiente_message = ""
    humedad_ambiente_color = "success"
    if target_humedad_ambiente < 40:
        humedad_ambiente_message = "⚠ Humedad ambiental baja, considere humidificar."
        humedad_ambiente_color = "danger"
    elif target_humedad_ambiente > 60:
        humedad_ambiente_message = "⚠ Humedad ambiental alta, riesgo de moho."
        humedad_ambiente_color = "warning"
    else:
        humedad_ambiente_message = "✅ Humedad ambiental óptima."

    return (
        html.Div(""), False, "warning",  # Ocultar alerta de conexión
        html.Div(humedad_message, className="mb-0"), True, humedad_color,
        html.Div(temperatura_message, className="mb-0"), True, temperatura_color,
        html.Div(humedad_ambiente_message, className="mb-0"), True, humedad_ambiente_color
    )

# Callback para tabla y gráficos
@app.callback(
    [Output('data-table', 'data'),
     Output('data-table', 'style_data_conditional'),
     Output('data-table', 'style_data'),
     Output('data-table', 'style_header'),
     Output('humidity-bar-graph', 'figure'),
     Output('temperature-line-graph', 'figure'),
     Output('humedad-ambiente-bar-graph', 'figure'),
     Output('tasks-text', 'children'),
     Output('tasks-bar-style', 'style'),
     Output('pending-text', 'children'),
     Output('pending-bar-style', 'style')],
    [Input('interval-component', 'n_intervals')]
)
def update_table_and_graphs(n):
    global is_connected, target_humedad, data_history
    table_data = [{"timestamp": row[0], "humedad": row[1], "temperatura": row[3], "humedad_ambiente": row[4]} for row in data_history]
    table_style_conditional = [{'if': {'state': 'active'}, 'backgroundColor': '#495057', 'color': '#e0e0e0'}] if not is_connected else []
    table_style_data = {'backgroundColor': '#2c3b41', 'color': '#e0e0e0', 'border': '1px solid #4b5e6b'}
    table_style_header = {'backgroundColor': '#007bff', 'color': 'white', 'fontWeight': 'bold', 'border': 'none'}

    # Gráfico de humedad del suelo
    bar_fig = go.Figure()
    if is_connected and data_history:
        timestamps = [row[0] for row in data_history]
        humidities = [row[1] for row in data_history]
        colors = ['#ff4d4d' if h < 30 or h > 80 else '#007bff' for h in humidities]
        bar_fig.add_trace(go.Bar(x=timestamps, y=humidities, marker_color=colors))
        bar_fig.update_layout(
            title="Tendencia de Humedad Suelo",
            xaxis_title="Hora",
            yaxis_title="Humedad (%)",
            yaxis_range=[0, 100],
            height=300,
            margin=dict(t=40, b=40, l=40, r=40),
            paper_bgcolor='#1e2b33',
            plot_bgcolor='#1e2b33',
            font={'color': '#e0e0e0'},
            xaxis=dict(gridcolor='#4b5e6b'),
            yaxis=dict(gridcolor='#4b5e6b')
        )
    else:
        bar_fig.add_annotation(
            text="Desconectado",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=20, color='#888'),
            opacity=0.7
        )
        bar_fig.update_layout(
            height=300,
            margin=dict(t=40, b=40, l=40, r=40),
            paper_bgcolor='#1e2b33',
            plot_bgcolor='#1e2b33',
            font={'color': '#e0e0e0'}
        )

    # Gráfico de temperatura
    line_fig = go.Figure()
    if is_connected and data_history:
        timestamps = [row[0] for row in data_history]
        temperatures = [row[3] for row in data_history]
        colors = ['#ff4d4d' if t < 15 or t > 35 else '#ff4d4d' for t in temperatures]
        line_fig.add_trace(go.Scatter(
            x=timestamps,
            y=temperatures,
            mode='lines+markers',
            name='Temperatura (°C)',
            line=dict(color='#ff4d4d', width=2, shape='spline'),
            marker=dict(size=8, color=colors)
        ))
        line_fig.update_layout(
            title="Tendencia de Temperatura",
            xaxis_title="Hora",
            yaxis_title="Temperatura (°C)",
            yaxis_range=[0, 50],
            height=300,
            margin=dict(t=40, b=40, l=40, r=40),
            paper_bgcolor='#1e2b33',
            plot_bgcolor='#1e2b33',
            font={'color': '#e0e0e0'},
            xaxis=dict(gridcolor='#4b5e6b'),
            yaxis=dict(gridcolor='#4b5e6b')
        )
    else:
        line_fig.add_annotation(
            text="Desconectado",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=20, color='#888'),
            opacity=0.7
        )
        line_fig.update_layout(
            height=300,
            margin=dict(t=40, b=40, l=40, r=40),
            paper_bgcolor='#1e2b33',
            plot_bgcolor='#1e2b33',
            font={'color': '#e0e0e0'}
        )

    # Gráfico de humedad ambiental
    hum_amb_fig = go.Figure()
    if is_connected and data_history:
        timestamps = [row[0] for row in data_history]
        hum_ambientes = [row[4] for row in data_history]
        colors = ['#ff4d4d' if h < 30 or h > 80 else '#1cc88a' for h in hum_ambientes]
        hum_amb_fig.add_trace(go.Bar(x=timestamps, y=hum_ambientes, marker_color=colors))
        hum_amb_fig.update_layout(
            title="Humedad Ambiental",
            xaxis_title="Hora",
            yaxis_title="Humedad Ambiental (%)",
            yaxis_range=[0, 100],
            height=300,
            margin=dict(t=40, b=40, l=40, r=40),
            paper_bgcolor='#1e2b33',
            plot_bgcolor='#1e2b33',
            font={'color': '#e0e0e0'},
            xaxis=dict(gridcolor='#4b5e6b'),
            yaxis=dict(gridcolor='#4b5e6b')
        )
    else:
        hum_amb_fig.add_annotation(
            text="Desconectado",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=20, color='#888'),
            opacity=0.7
        )
        hum_amb_fig.update_layout(
            height=300,
            margin=dict(t=40, b=40, l=40, r=40),
            paper_bgcolor='#1e2b33',
            plot_bgcolor='#1e2b33',
            font={'color': '#e0e0e0'}
        )

    valores_en_ultima_hora = obtener_valores_ultima_hora(data_history)
    if is_connected:
        tiempo_riego = (30 - target_humedad) * 2 if target_humedad < 30 else 0
        tasks_text = f"Tiempo riego estimado: {tiempo_riego:.0f} min" if tiempo_riego > 0 else "Riego no necesario"
        tasks_bar_width = f"{min(tiempo_riego * 3, 100)}%"
        conteo_optimo = sum(1 for v in valores_en_ultima_hora if 30 <= v[1] <= 80)
        pending_text = f"Lecturas óptimas: {conteo_optimo}"
        pending_bar_width = f"{min(conteo_optimo * 10, 100)}%"
    else:
        tasks_text = "Desconectado"
        tasks_bar_width = "0%"
        pending_text = "Desconectado"
        pending_bar_width = "0%"

    return (
        table_data,
        table_style_conditional,
        table_style_data,
        table_style_header,
        bar_fig,
        line_fig,
        hum_amb_fig,
        tasks_text,
        {"width": tasks_bar_width, "backgroundColor": "#1cc88a"},
        pending_text,
        {"width": pending_bar_width, "backgroundColor": "#f6c23e"}
    )

if __name__ == '__main__':
    # app.run(debug=True, use_reloader=False)
    app.run(host='0.0.0.0', port=8050, debug=True, use_reloader=False)