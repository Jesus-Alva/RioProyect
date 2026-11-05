# Distribuidora Río Claro

## 1. Definición y analisis del Proyecto

Toda la información presentada es ficticia, para dar cumplimiento al *proyecto Fase 2*

#### By: Jesús Alva Bustamante

### ¿Quienes son?

Río Claro es una distribuidora familiar de productos de limpieza e higiene con 22 años en el mercado, 140 empleados y 5 sucursales 

(Guadalajara, Zapopan, León, Querétaro y Aguascalientes). Vende a hoteles, restaurantes, escuelas y pequeñas tiendas. 

### Problematica Identificada: 
- Datos dispersos y sin normalizar: facturas, correos, contratos e historial de clientes en formatos heterogéneos.
- Ausencia de un repositorio único y gobernado (sin catálogo de datos, sin dueños del dato, sin políticas de calidad).
- Procesos manuales sin controles automáticos (validación de facturas, conciliación, triage de solicitudes).
- Falta de una capa de conocimiento estructurado (RAG, base vectorial, ontologías) que la IA necesita para responder con precisión.

### Roles identificados: 
- Rol: Directivo / Administrador General (Ernesto)
- Rol: Analista / Operador de Cuentas por Pagar  (Laura)
- Rol: Gerente de Sucursal / Atención al Cliente (Mariana)
- Rol: Operador de Bodega / Almacén (Toño)
- Rol: Administrador de TI / Soporte Técnico (Carlos)

### Solucion Propúesta
Creacion de un sistema web que se encarge de automatizar procesos mediante ayuda de una IA que consuma informacion centralizada de los clientes y las distintas sucursales.

### Puntos clave: 
- Presupuesto limitado: la dirección aprueba un piloto pequeño; hay que justificar cada servicio que se cree.
- Sin personal técnico: la solución debe
poder usarla gente de bodega y ventas, algunos solo desde el celular o por voz. 
- No se puede “empezar de cero”: la operación no se detiene; los
datos se ordenan mientras la empresa sigue vendiendo. 
- Confianza: Laura y los gerentes temen que la IA “los reemplace” o que invente cifras; se
debe mostrar que la IA apoya y que siempre hay una persona que revisa.
- Capacidad para administrar las 5 sucursales
- Capacidad para segmentar la informacion por cada sucrsual  

## 2. Modulos preevistos del sistema
### Módulo Operador de Bodega (Toño)
1. Interfaz *mobile-first* (diseñada para celular) con un botón de entrada por voz (Speech-to-Text).
2. Capacidad de hacer consultas en lenguaje natural (ej. "¿Cuánto cloro de litro nos queda?") y recibir respuestas sintetizadas (Text-to-Speech opcional).

### Módulo Administrador de TI (Carlos)
1. Monitoreo del estado del sistema y de las conexiones a Azure.
2. Gestión de identidades (simulada con el selector de roles) basada en Entra ID.
3. Control de seguridad: Capacidad de "pausar" o limitar el acceso a los agentes si algo falla.

### Funcionalidades Transversales de IA Responsable (UI/UX)
Para cumplir con los criterios del examen AI-901, la interfaz web incluirá:
- **Transparencia:** Aviso visible en el chat: *"Estás interactuando con un asistente de IA. Las respuestas se basan en documentos oficiales"*.
- **Transparencia (Fuentes):** Cada respuesta del agente incluirá una cita al documento del cual extrajo la información (ej. `Fuente: factura_001.pdf`).
- **Rendición de cuentas (Human-in-the-loop):** En el módulo de Laura, las facturas con confianza menor a 0.8 se mostrarán en un panel de "Revisión Manual" requiriendo su aprobación antes de registrarse.
- **Equidad:** El agente consulta un índice centralizado, garantizando que las respuestas no favorezcan a ninguna sucursal por tener "mejores datos".
### Modulo Directivos:
1. Modulo dashboard para generar un reporte de ventas en el que las 5 sucursales coincidan y un piloto que cueste lo previsto. .
2. Modulo para concer el inventario de cada sucursal
3. Modulo para visualizacion de facturas
#### Funciones esperadas:
1. Generar Reporte de ventas para la direccion por producto
2. Filtrado de informacion del reporte por sucursal
3. Gestion de sucursales (Guadalajara, Zapopan, León, Querétaro y Aguascalientes)

### Modulo Analista
1. Extraer la informacion (proveedor, fecha y total) de los proveedores de las facturas

### Modulo Gerente de Sucursal
Lectura de archivos para extraccion de informacion mediante IA (Punto 3 apartado 1)

### Modulo Operador de Bodega

### LO que debe de incluir el modelo de IA
[]Uso desde el celular o por voz

### Funciones generales
1. Modulo en donde los proveedores carguen sus facturas (el sistema debe indexar los documentos en Azure AI Search)

## 3. Implementacion

### 3.1 Capa de datos
Uno de los problemas con los que se tiene que lidiar antes de generar cualquier sistema y poner a los AGENTES a consumir datos, es la falta de organizacion de la informacion, pues cito "El reto no es solo *conectar un modelo*: primero tienen que entender por qué la empresa no está lista, ordenar lo indispensable y después construir", Por lo que, como en la problematica identificada se indica, los datos/inbformacion estan dispersos. 
Para solventar este punto se propone lo siguiente:
|#|Desorden Identificado|Acción mínima antes de conectar la IA|Servicio Azure que lo resuelve|
|-|-|-|-|
|1|Facturas en PDF y fotos de WhatsApp, sin carpeta estándar|Crear un contenedor de ingesta único en Blob Storage los compradores suben ahí (o reenvían a una dirección).| Azure Blob Storage|
|2|“Cloro 1L”, “CLORO LITRO” y “Blanqueador 1000ml” son el mismo producto|Definir un catálogo maestro de productos (una tabla con clave única y sinónimos). El agente consulta esa tabla, no los Excels de sucursal.|	Azure SQL / tabla en Blob + índice en AI Search|
|3|Tres versiones de la política de devoluciones|Elegir una versión vigente, marcarla como “aprobada por dirección” y subirla como fuente de conocimiento del agente.|Azure AI Search (índice de conocimiento)|
|4|Contraseña compartida; nóminas y precios visibles para todos|No conectar datos sensibles al modelo. El agente solo accede a lo que necesita por rol. |Microsoft Entra ID + Key Vault|
|5|Quejas sin historial central|Un formulario/buzón simple que registre texto y sucursal; luego el agente puede analizar sentimiento y temas.|Blob Storage + Language Service (opcional)|
 
## Evidencia

Links directos a los servicios creados

#### 1.- Grupo de Recursos (El contenedor principal)

- Enlace: [Ver Grupo de Recursos](https://portal.azure.com/#resource/subscriptions/8a105d2e-7fed-45bc-bb81-83c1cd12488b/resourceGroups/rg-rioclaro-data-piloto/overview)

Qué revisar: Aquí deberías ver la lista de todos los recursos que creamos (Storage, Search, Foundry, etc.).

#### 2.- Blob Storage (Almacén de facturas)
- Enlace: [Ver Cuenta de Almacenamiento](https://portal.azure.com/#resource/subscriptions/8a105d2e-7fed-45bc-bb81-83c1cd12488b/resourceGroups/rg-rioclaro-data-piloto/providers/Microsoft.Storage/storageAccounts/strioclarofacturas/overview)

Qué revisar: En el menú de la izquierda, busca la sección "Contenedores" (Data storage > Containers). Ahí debe aparecer el contenedor llamado facturas-raw.

#### 3.- Document Intelligence (Extractor de facturas)
- Enlace: [Ver Document Intelligence](https://portal.azure.com/#resource/subscriptions/8a105d2e-7fed-45bc-bb81-83c1cd12488b/resourceGroups/rg-rioclaro-data-piloto/providers/Microsoft.CognitiveServices/accounts/di-rioclaro-facturas/overview)

Qué revisar: En el menú izquierdo, ve a "Keys and Endpoint". Ahí encontrarás el Endpoint (https://di-rioclaro-facturas.cognitiveservices.azure.com/) que usamos en las variables de entorno.

(Opcional) Puedes ir a "Document Intelligence Studio" en el menú superior para probar subir un PDF de prueba visualmente.

#### 4.- Azure AI Search (El índice seguro)
- Enlace: [Ver Azure AI Search](https://portal.azure.com/#resource/subscriptions/8a105d2e-7fed-45bc-bb81-83c1cd12488b/resourceGroups/rg-rioclaro-data-piloto/providers/Microsoft.Search/searchServices/srch-rioclaro/overview)

Qué revisar: En el menú izquierdo, busca "Índices" (Indexes). Si el script de Python corrió bien, deberías ver el índice rioclaro-index con su campo security_id.

#### 5.- Microsoft Foundry (El cerebro de la IA)
- Enlace: [Ver Recurso de Foundry](https://portal.azure.com/#resource/subscriptions/8a105d2e-7fed-45bc-bb81-83c1cd12488b/resourceGroups/rg-rioclaro-data-piloto/providers/Microsoft.CognitiveServices/accounts/foundry-rioclaro-575/overview)

Qué revisar: En la parte superior, busca el botón "Go to Foundry portal" (Ir al portal de Foundry). Eso te abrirá la interfaz donde crearemos a los agentes en la Fase 2.

(Nota: El nombre del recurso es foundry-rioclaro-575 por el conflicto de nombre que resolvimos).

#### 6. Key Vault (Bóveda de secretos)
Enlace: [Ver Key Vault](https://portal.azure.com/#resource/subscriptions/8a105d2e-7fed-45bc-bb81-83c1cd12488b/resourceGroups/rg-rioclaro-data-piloto/providers/Microsoft.KeyVault/vaults/kv-rioclaro-piloto/overview)

Qué revisar: Aquí guardaremos las llaves en el futuro. Por ahora puedes ver que el servicio está activo.



![Inicio de documentacion para evidencia](evidencia-img/evidencia-analisis01.png)