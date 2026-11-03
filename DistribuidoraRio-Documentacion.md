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

## 2. Modulos preevistos del sistema
> EL sistema debe de contar con los siguientes modulos
### Modulo Directivos:
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

![Inicio de documentacion para evidencia](evidencia-img/evidencia-analisis01.png)