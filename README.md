# VisionMatch AI — Python Edition

Chatbot de recomendación de televisores migrado de Node.js a Python.
Devuelve las **5 mejores opciones** de TV usando KMeans clustering + Azure SQL.

## Arquitectura

```
Usuario (Navegador)
    │  POST { message }
    ▼
Azure Static Web Apps  ←── index.html
    │
    │  POST /api/chat
    ▼
Azure Functions (Python 3.11)
    ├── shared/parser.py        ← extrae pulgadas, presupuesto, familia
    ├── shared/clustering.py    ← KMeans: asigna cluster al perfil del usuario
    ├── shared/recommender.py   ← consulta SQL + score → top 5
    └── shared/db.py            ← conexión Azure SQL
    │
    ├── model/kmeans_model.pkl  ← modelo pre-entrenado (incluido en deploy)
    │
    ▼
Azure SQL Database
    └── dbo.hd_televisores
```

## Setup local

### 1. Requisitos
- Python 3.11+
- Azure Functions Core Tools v4: `npm install -g azure-functions-core-tools@4`
- ODBC Driver 18 for SQL Server (instalar desde Microsoft)

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
pip install python-dotenv  # solo para training local
```

### 3. Configurar variables de entorno
Edita `local.settings.json`:
```json
{
  "Values": {
    "SQL_SERVER": "tu-server.database.windows.net",
    "SQL_DATABASE": "tu-database",
    "SQL_USER": "tu-usuario",
    "SQL_PASSWORD": "tu-password"
  }
}
```

### 4. Entrenar el modelo KMeans (una vez)
```bash
python training/train_kmeans.py
```
Esto genera `model/kmeans_model.pkl`.

### 5. Correr localmente
```bash
func start
```
La función estará en: `http://localhost:7071/api/chat`

Test rápido:
```bash
curl -X POST http://localhost:7071/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"55 pulgadas QLED hasta 3000 soles"}'
```

## Deploy a Azure (suscripción gratuita)

### Backend — Azure Functions
```bash
# Crear la Function App (una vez)
az functionapp create \
  --resource-group tu-resource-group \
  --consumption-plan-location eastus \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --name visionmatch-fn \
  --storage-account tu-storage

# Configurar variables de entorno en Azure
az functionapp config appsettings set \
  --name visionmatch-fn \
  --resource-group tu-resource-group \
  --settings \
    SQL_SERVER="tu-server.database.windows.net" \
    SQL_DATABASE="tu-database" \
    SQL_USER="tu-usuario" \
    SQL_PASSWORD="tu-password"

# Publicar (incluye el .pkl en el deploy)
func azure functionapp publish visionmatch-fn
```

### Frontend — Azure Static Web Apps
1. Sube `index.html` a un repositorio GitHub
2. Crea un Static Web App en Azure apuntando a ese repo
3. Edita el `API_URL` en `index.html` con la URL de tu Function App

## Estructura de archivos

```
visionmatch-python/
├── chat/
│   ├── __init__.py        ← Azure Function principal
│   └── function.json      ← binding HTTP
├── shared/
│   ├── parser.py          ← regex: extrae pulgadas, presupuesto, familia
│   ├── db.py              ← conexión Azure SQL (pyodbc)
│   ├── recommender.py     ← top 5 con score multidimensional
│   └── clustering.py      ← carga modelo .pkl y predice cluster
├── model/
│   └── kmeans_model.pkl   ← generado por train_kmeans.py
├── training/
│   └── train_kmeans.py    ← script local para entrenar/reentrenar
├── index.html             ← frontend (sube a Static Web Apps)
├── host.json
├── requirements.txt
├── local.settings.json    ← NO subir al repo (en .gitignore)
└── .gitignore
```

## Respuesta JSON del endpoint

```json
{
  "message": "📺 Aquí tus 5 mejores opciones...",
  "cluster_id": 2,
  "products": [
    {
      "rank": 1,
      "name": "Smart TV Samsung 55\" QLED 4K",
      "familia": "QLED",
      "pulgadas": 55,
      "vendedor": "Falabella",
      "precio": 2899.0,
      "url": "https://...",
      "imagen": "https://..."
    },
    ...
  ]
}
```

## Costos en Azure (suscripción gratuita)

| Servicio           | Plan        | Costo estimado |
|--------------------|-------------|----------------|
| Azure Functions    | Consumption | Gratis (1M llamadas/mes) |
| Static Web Apps    | Free tier   | Gratis |
| Azure SQL          | Basic (5 DTU)| ~$5 USD/mes |
| OpenAI API         | Pay per use | ~$0.002/query |
