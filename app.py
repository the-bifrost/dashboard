from flask import Flask, request, jsonify
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt
from collections import defaultdict, deque
import time
import json
import os

app = Flask(__name__)
socketio = SocketIO(app)

# Configurações do MQTT
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPICS = ["#"]

# Armazenamento de histórico (tópico: deque de valores)
HISTORY_LENGTH = 50
sensor_history = defaultdict(lambda: deque(maxlen=HISTORY_LENGTH))

# Armazenamento de nomes personalizados
CUSTOM_NAMES_FILE = 'custom_names.json'
custom_names = {}

# Carregar nomes personalizados se existirem
if os.path.exists(CUSTOM_NAMES_FILE):
    try:
        with open(CUSTOM_NAMES_FILE, 'r') as f:
            custom_names = json.load(f)
    except:
        pass

# Cliente MQTT
client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    print(f"Conectado ao MQTT Broker com código {rc}")
    for topic in MQTT_TOPICS:
        client.subscribe(topic)

def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    topic = msg.topic
    
    try:
        # Tentar converter para float se possível
        numeric_value = float(payload)
        sensor_history[topic].append((time.time(), numeric_value))
    except ValueError:
        # Manter como string se não for numérico
        sensor_history[topic].append((time.time(), payload))
    
    print(f"Mensagem recebida: {topic} -> {payload}")
    socketio.emit('mqtt_message', {
        'topic': topic,
        'payload': payload,
        'history': list(sensor_history[topic])[-10:]  # Enviar último histórico
    })

client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

@app.route('/update_name', methods=['POST'])
def update_name():
    data = request.json
    topic = data.get('topic')
    new_name = data.get('name')
    
    if topic:
        custom_names[topic] = new_name
        # Salvar em arquivo
        with open(CUSTOM_NAMES_FILE, 'w') as f:
            json.dump(custom_names, f)
        return jsonify(success=True)
    return jsonify(success=False)

@app.route('/get_history')
def get_history():
    topic = request.args.get('topic')
    if topic in sensor_history:
        return jsonify(history=list(sensor_history[topic]))
    return jsonify(history=[])

@app.route('/')
def index():
    html = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Bifrost Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.1/socket.io.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <script>
            tailwind.config = {
                theme: {
                    extend: {
                        colors: {
                            primary: '#41BDF5',
                            secondary: '#0075D4',
                            accent: '#FF9500',
                            dark: '#121212',
                            card: '#1E1E1E',
                            light: '#2D2D2D'
                        }
                    }
                }
            }
        </script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
            :root {
                --primary: #41BDF5;
                --secondary: #0075D4;
                --accent: #FF9500;
                --dark: #121212;
                --card: #1E1E1E;
                --light: #2D2D2D;
            }
            body {
                font-family: 'Poppins', sans-serif;
                background-color: var(--dark);
                color: #FFFFFF;
            }
            .sensor-card {
                background-color: var(--card);
                border-radius: 16px;
                transition: all 0.3s ease;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
                overflow: hidden;
            }
            .sensor-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 6px 25px rgba(65, 189, 245, 0.2);
            }
            .card-header {
                background-color: rgba(65, 189, 245, 0.15);
                padding: 16px;
                border-bottom: 1px solid var(--light);
            }
            .chart-container {
                height: 120px;
                position: relative;
            }
            .pulse {
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0% { box-shadow: 0 0 0 0 rgba(65, 189, 245, 0.4); }
                70% { box-shadow: 0 0 0 10px rgba(65, 189, 245, 0); }
                100% { box-shadow: 0 0 0 0 rgba(65, 189, 245, 0); }
            }
            .add-btn {
                background: linear-gradient(135deg, var(--primary), var(--secondary));
                transition: all 0.3s;
            }
            .add-btn:hover {
                opacity: 0.9;
                transform: scale(1.05);
            }
            .topic-badge {
                background-color: rgba(255, 149, 0, 0.15);
                color: var(--accent);
                font-size: 0.7rem;
            }
        </style>
    </head>
    <body class="min-h-screen">
        <!-- Top Bar -->
        <div class="bg-card py-4 px-6 border-b border-light flex justify-between items-center">
            <div class="flex items-center">
                <div class="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center mr-3">
                    <i class="fas fa-home text-primary"></i>
                </div>
                <h1 class="text-2xl font-bold">Bifrost Dashboard</h1>
            </div>
            <div class="flex items-center">
                <div class="w-3 h-3 rounded-full bg-green-500 mr-2"></div>
                <span class="text-green-500">Conectado</span>
            </div>
        </div>
        
        <!-- Main Content -->
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <!-- Input Section -->
            <div class="bg-card rounded-xl p-6 mb-8 border border-light">
                <h2 class="text-xl font-semibold mb-4">Adicionar Novo Sensor</h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                        <label class="block text-sm font-medium mb-2 text-gray-400">Tópico MQTT</label>
                        <input id="topicInput" type="text" placeholder="Ex: sensor/temperatura" 
                               class="w-full px-4 py-3 bg-light border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent">
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-2 text-gray-400">Nome Amigável (Opcional)</label>
                        <input id="friendlyName" type="text" placeholder="Ex: Temperatura Sala" 
                               class="w-full px-4 py-3 bg-light border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent">
                    </div>
                    <div class="flex items-end">
                        <button onclick="addSensorCard()" class="w-full add-btn text-white font-medium rounded-lg px-6 py-3 flex items-center justify-center gap-2">
                            <i class="fas fa-plus"></i>
                            Adicionar Sensor
                        </button>
                    </div>
                </div>
                
                <!-- Recent Topics -->
                <div class="mt-6">
                    <h3 class="text-lg font-medium mb-3">Tópicos Recentes</h3>
                    <div id="recentTopics" class="flex flex-wrap gap-2">
                        <!-- Recent topics will be added here -->
                    </div>
                </div>
            </div>
            
            <!-- Cards Grid -->
            <div id="sensorCards" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                <!-- Cards will be added here dynamically -->
            </div>
            
            <!-- Empty State -->
            <div id="emptyState" class="text-center py-16">
                <div class="mx-auto w-24 h-24 rounded-full bg-card flex items-center justify-center mb-6">
                    <i class="fas fa-satellite-dish text-4xl text-primary"></i>
                </div>
                <h3 class="text-xl font-semibold mb-2">Nenhum sensor adicionado</h3>
                <p class="text-gray-400 max-w-md mx-auto">
                    Adicione sensores usando o formulário acima para começar a monitorar
                </p>
            </div>
        </div>

        <script>
            const socket = io();
            const sensorCards = {};
            const recentTopics = new Set();
            const customNames = {};
            
            // Carregar nomes personalizados do localStorage
            function loadCustomNames() {
                const savedNames = localStorage.getItem('customNames');
                if (savedNames) {
                    try {
                        Object.assign(customNames, JSON.parse(savedNames));
                    } catch (e) {
                        console.error('Error loading custom names:', e);
                    }
                }
            }
            
            // Salvar nomes personalizados no localStorage
            function saveCustomNames() {
                localStorage.setItem('customNames', JSON.stringify(customNames));
            }
            
            // Inicializar
            loadCustomNames();
            
            // Atualizar estado vazio
            function checkEmptyState() {
                const emptyState = document.getElementById('emptyState');
                if (Object.keys(sensorCards).length > 0) {
                    emptyState.classList.add('hidden');
                } else {
                    emptyState.classList.remove('hidden');
                }
            }
            
            // Processar mensagem MQTT
            socket.on('mqtt_message', (data) => {
                const { topic, payload, history } = data;
                
                // Adicionar tópico aos recentes
                if (!recentTopics.has(topic)) {
                    recentTopics.add(topic);
                    updateRecentTopics();
                }
                
                // Atualizar card existente
                if (sensorCards[topic]) {
                    const card = sensorCards[topic];
                    
                    // Atualizar valor
                    card.querySelector('.current-value').textContent = payload;
                    
                    // Adicionar ao histórico
                    const timestamp = Date.now() / 1000;
                    card.chartData.labels.push(new Date().toLocaleTimeString());
                    card.chartData.datasets[0].data.push(payload);
                    
                    // Manter apenas os últimos pontos
                    if (card.chartData.labels.length > 15) {
                        card.chartData.labels.shift();
                        card.chartData.datasets[0].data.shift();
                    }
                    
                    // Atualizar gráfico
                    card.chart.update();
                    
                    // Efeito de pulsação
                    card.classList.add('pulse');
                    setTimeout(() => card.classList.remove('pulse'), 1000);
                }
            });
            
            // Atualizar lista de tópicos recentes
            function updateRecentTopics() {
                const container = document.getElementById('recentTopics');
                container.innerHTML = '';
                
                recentTopics.forEach(topic => {
                    const badge = document.createElement('div');
                    badge.className = 'topic-badge px-3 py-1.5 rounded-full cursor-pointer hover:bg-accent/25';
                    badge.textContent = topic;
                    badge.onclick = () => {
                        document.getElementById('topicInput').value = topic;
                    };
                    container.appendChild(badge);
                });
            }
            
            // Obter ícone para o tópico
            function getIconForTopic(topic) {
                const topicLower = topic.toLowerCase();
                if (topicLower.includes('temp') || topicLower.includes('temperatura')) {
                    return 'fa-temperature-high';
                } else if (topicLower.includes('umid') || topicLower.includes('humidity')) {
                    return 'fa-droplet';
                } else if (topicLower.includes('luz') || topicLower.includes('light')) {
                    return 'fa-lightbulb';
                } else if (topicLower.includes('press') || topicLower.includes('pressure')) {
                    return 'fa-gauge-high';
                } else if (topicLower.includes('gas') || topicLower.includes('fumaca') || topicLower.includes('smoke')) {
                    return 'fa-smog';
                } else if (topicLower.includes('door') || topicLower.includes('porta')) {
                    return 'fa-door-open';
                } else if (topicLower.includes('motion') || topicLower.includes('movimento')) {
                    return 'fa-person-walking';
                }
                return 'fa-wave-square';
            }
            
            // Criar gráfico
            function createChart(canvas, initialData = []) {
                const ctx = canvas.getContext('2d');
                const data = {
                    labels: Array(initialData.length).fill(''),
                    datasets: [{
                        label: 'Valor',
                        data: initialData,
                        borderColor: '#41BDF5',
                        backgroundColor: 'rgba(65, 189, 245, 0.1)',
                        borderWidth: 2,
                        pointRadius: 0,
                        tension: 0.4,
                        fill: true
                    }]
                };
                
                return new Chart(ctx, {
                    type: 'line',
                    data: data,
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false },
                            tooltip: { enabled: false }
                        },
                        scales: {
                            x: { display: false },
                            y: { 
                                display: false,
                                suggestedMin: Math.min(...initialData) - 2,
                                suggestedMax: Math.max(...initialData) + 2
                            }
                        },
                        interaction: { mode: 'nearest', intersect: false },
                        animation: { duration: 0 }
                    }
                });
            }
            
            // Adicionar card de sensor
            async function addSensorCard() {
                const topicInput = document.getElementById('topicInput');
                const friendlyNameInput = document.getElementById('friendlyName');
                const topic = topicInput.value.trim();
                const friendlyName = friendlyNameInput.value.trim();
                
                if (!topic) {
                    alert('Por favor, digite um tópico válido');
                    return;
                }
                
                if (sensorCards[topic]) {
                    alert('Este sensor já está sendo monitorado');
                    return;
                }

                // Salvar nome amigável se fornecido
                if (friendlyName) {
                    customNames[topic] = friendlyName;
                    saveCustomNames();
                    
                    // Enviar para o servidor
                    fetch('/update_name', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ topic, name: friendlyName })
                    });
                }

                const icon = getIconForTopic(topic);
                const cardId = `card-${Date.now()}`;
                const displayName = friendlyName || customNames[topic] || topic;
                
                // Obter histórico do servidor
                const historyResponse = await fetch(`/get_history?topic=${encodeURIComponent(topic)}`);
                const historyData = await historyResponse.json();
                const initialData = historyData.history.map(item => item[1]);
                
                const card = document.createElement('div');
                card.id = cardId;
                card.className = 'sensor-card';
                card.innerHTML = `
                    <div class="card-header flex justify-between items-start">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                                <i class="${icon} text-lg text-primary"></i>
                            </div>
                            <div>
                                <h2 class="font-semibold sensor-name" data-topic="${topic}">${displayName}</h2>
                                <div class="topic-badge px-2 py-0.5 rounded-full inline-block text-xs mt-1">${topic}</div>
                            </div>
                        </div>
                        <div class="flex gap-2">
                            <button onclick="editName('${topic}')" class="text-gray-400 hover:text-primary">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button onclick="removeCard('${topic}', '${cardId}')" class="text-gray-400 hover:text-red-500">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    </div>
                    
                    <div class="p-5">
                        <div class="text-3xl font-bold text-center mb-4 current-value">--</div>
                        <div class="chart-container">
                            <canvas id="chart-${cardId}"></canvas>
                        </div>
                    </div>
                    
                    <div class="px-5 py-3 bg-light flex justify-between items-center">
                        <div class="text-sm text-gray-400">
                            <i class="fas fa-clock mr-1"></i> Atualizado: <span class="update-time">agora</span>
                        </div>
                        <div class="flex items-center">
                            <span class="w-2 h-2 rounded-full bg-green-500 mr-2"></span>
                            <span class="text-xs">Online</span>
                        </div>
                    </div>
                `;
                
                document.getElementById('sensorCards').appendChild(card);
                sensorCards[topic] = card;
                
                // Inicializar gráfico
                const canvas = card.querySelector(`#chart-${cardId}`);
                card.chart = createChart(canvas, initialData);
                card.chartData = {
                    labels: Array(initialData.length).fill(''),
                    datasets: [{ data: initialData }]
                };
                
                // Limpar inputs
                topicInput.value = '';
                friendlyNameInput.value = '';
                checkEmptyState();
            }
            
            // Editar nome
            function editName(topic) {
                const card = sensorCards[topic];
                if (!card) return;
                
                const nameElement = card.querySelector('.sensor-name');
                const currentName = nameElement.textContent;
                
                const newName = prompt('Digite o novo nome para este sensor:', currentName);
                if (newName && newName.trim() !== currentName) {
                    nameElement.textContent = newName.trim();
                    customNames[topic] = newName.trim();
                    saveCustomNames();
                    
                    // Enviar para o servidor
                    fetch('/update_name', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ topic, name: newName.trim() })
                    });
                }
            }
            
            // Remover card
            function removeCard(topic, cardId) {
                if (sensorCards[topic]) {
                    const card = document.getElementById(cardId);
                    if (card) {
                        // Destruir gráfico antes de remover
                        if (card.chart) {
                            card.chart.destroy();
                        }
                        card.remove();
                    }
                    delete sensorCards[topic];
                    checkEmptyState();
                }
            }
            
            // Inicializar estado vazio
            checkEmptyState();
        </script>
    </body>
    </html>
    """
    return html

@socketio.on('connect')
def handle_connect():
    print("Cliente WebSocket conectado")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)