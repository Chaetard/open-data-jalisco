# Manifiesto de Open Data Jalisco

## 1. Nombre del proyecto

**Open Data Jalisco** es una iniciativa ciudadana, técnica, apartidista y open source para recopilar, preservar, organizar, consultar y verificar información pública municipal del estado de Jalisco, México.

El primer piloto territorial del proyecto será el municipio de **Tala, Jalisco**.

El objetivo no es sustituir a las autoridades, ni emitir acusaciones, ni interpretar políticamente la información pública. El objetivo es construir una infraestructura abierta que facilite a cualquier persona consultar documentos públicos, entenderlos mejor, verificar su procedencia y participar de forma más informada en la vida pública de su municipio.

---

## 2. Declaración de propósito

La información pública existe para ser consultada, reutilizada y entendida por la ciudadanía.

Sin embargo, en la práctica, muchos documentos públicos se encuentran dispersos en portales distintos, formatos difíciles de consultar, archivos PDF, hojas de cálculo, páginas poco indexadas, enlaces rotos, estructuras inconsistentes o sistemas que no facilitan la búsqueda histórica.

Open Data Jalisco nace para reducir esa fricción.

El proyecto busca crear una capa abierta de consulta documental sobre información pública municipal, manteniendo siempre trazabilidad hacia las fuentes oficiales.

La visión es que una persona pueda preguntar:

> “¿Qué contratos públicos relacionados con obra hubo en Tala durante 2021?”

Y el sistema pueda responder con documentos, fechas, fuentes, enlaces oficiales, fragmentos relevantes y evidencia verificable.

---

## 3. Principios fundamentales

Open Data Jalisco se rige por los siguientes principios:

### 3.1 Neutralidad política

El proyecto es apartidista.

No está diseñado para favorecer ni perjudicar a partidos, gobiernos, funcionarios, administraciones, candidatos, proveedores o grupos políticos.

El sistema no debe asumir corrupción, dolo, delito, responsabilidad administrativa ni mala fe.

Cuando existan posibles inconsistencias documentales, omisiones, contradicciones, faltantes o información insuficiente, el sistema podrá señalarlas de forma descriptiva y verificable, sin convertirlas en acusaciones.

Ejemplo aceptable:

> “No se encontró en la base un documento que respalde el monto total mencionado. Se recomienda consultar directamente al municipio o realizar una solicitud de información.”

Ejemplo no aceptable:

> “Esto demuestra corrupción.”

El proyecto debe incentivar la participación ciudadana informada, no la persecución política ni la desinformación.

---

### 3.2 Trazabilidad documental

La fuente de verdad no es la inteligencia artificial.

La fuente de verdad no es la base vectorial.

La fuente de verdad es el conjunto verificable formado por:

- documento original capturado;
- URL oficial de origen;
- fecha y hora de captura;
- hash criptográfico del archivo;
- metadata de procedencia;
- versión histórica del documento;
- manifest público del dataset cuando aplique.

Toda respuesta relevante del sistema debe poder rastrearse hacia documentos concretos.

---

### 3.3 Integridad y preservación

Los documentos capturados no deben modificarse.

Cuando un documento cambie en la fuente oficial, el sistema no debe reemplazar silenciosamente la versión anterior. Debe guardar una nueva versión, con nuevo hash, nueva fecha de captura y nueva metadata.

La base de datos puede actualizar índices, texto extraído, embeddings y metadata de procesamiento, pero el documento original capturado debe preservarse como evidencia histórica.

La base vectorial es únicamente un índice de recuperación semántica. No representa autoridad factual por sí misma.

---

### 3.4 Transparencia técnica

El código del proyecto será open source.

Los scrapers, pipelines de ingesta, procesadores documentales, esquemas, modelos de datos, manifiestos, documentación y criterios de contribución deberán estar disponibles públicamente cuando sea técnicamente posible.

La instancia oficial de producción podrá ser administrada por los mantenedores del proyecto, pero el código debe permitir que cualquier persona audite, ejecute, replique o mejore el sistema.

---

### 3.5 Acceso público y gratuito

El proyecto buscará ofrecer acceso gratuito a la consulta de información pública procesada.

La API pública podrá estar sujeta a límites razonables de uso, autenticación técnica, cuotas, rate limits o mecanismos similares para proteger la disponibilidad del servicio.

El uso de API keys no debe entenderse como una barrera comercial, sino como una medida operativa para evitar abuso, saturación o costos insostenibles.

---

### 3.6 Protección de datos personales

El hecho de que un documento sea público no significa que el proyecto deba amplificar innecesariamente datos personales.

Open Data Jalisco no tiene como finalidad perfilar individuos, exponer domicilios particulares, facilitar acoso, doxxing, persecución política o difusión innecesaria de datos sensibles.

Cuando los documentos oficiales contengan datos personales, el proyecto deberá procurar no destacarlos fuera del contexto documental original, especialmente si no son necesarios para responder una consulta ciudadana.

El sistema podrá conservar documentos públicos completos cuando provengan de fuentes oficiales, pero la interfaz, la API y el asistente conversacional deberán aplicar criterios de minimización, contexto y responsabilidad.

---

## 4. Alcance inicial

El alcance territorial inicial será:

- Tala, Jalisco.

El alcance futuro será:

- municipios del estado de Jalisco.

Los tipos de información pública a considerar en etapas iniciales incluyen:

- contratos;
- licitaciones;
- adjudicaciones;
- compras públicas;
- obra pública;
- reglamentos;
- actas;
- presupuestos;
- leyes de ingresos;
- egresos;
- nómina pública cuando sea procedente;
- directorios institucionales;
- documentos de transparencia;
- gacetas o medios oficiales municipales;
- información publicada en portales oficiales;
- información consultable mediante plataformas oficiales de transparencia.

La incorporación de nuevas fuentes deberá hacerse de forma documentada, auditable y preferentemente mediante configuración versionada.

---

## 5. Qué no es Open Data Jalisco

Open Data Jalisco no es:

- una autoridad fiscalizadora;
- una auditoría oficial;
- una fiscalía;
- un tribunal;
- una herramienta de propaganda;
- una herramienta partidista;
- una plataforma para acusar personas;
- una base de datos editable por actores externos;
- una sustitución de solicitudes formales de transparencia;
- una sustitución de fuentes oficiales;
- una garantía de completitud absoluta;
- una prueba automática de irregularidades;
- un sistema para publicar datos personales fuera de contexto.

El sistema puede ayudar a encontrar documentos, comparar información, detectar faltantes y señalar inconsistencias documentales. Pero no debe convertir esas señales en conclusiones jurídicas, penales, administrativas o políticas.

---

## 6. Participación ciudadana informada

El proyecto parte de una convicción sencilla:

> La ciudadanía no puede participar plenamente en la vida pública si la información existe, pero es difícil de encontrar, consultar o entender.

Open Data Jalisco busca facilitar que estudiantes, periodistas, desarrolladores, organizaciones civiles, investigadores, vecinos y cualquier persona interesada puedan consultar información pública municipal con mayor claridad.

Cuando el sistema detecte una posible falta de documentos, inconsistencias entre fuentes, ausencia de respaldo documental o información incompleta, deberá invitar al usuario a:

- revisar la fuente oficial;
- consultar documentos relacionados;
- realizar una solicitud formal de información;
- contactar a la unidad de transparencia correspondiente;
- reportar errores del dataset;
- contribuir con mejoras al proyecto;
- participar de manera informada en los mecanismos públicos disponibles.

El objetivo no es hacerle “la chamba” al ciudadano ni imponer una conclusión, sino reducir la fricción para que pueda preguntar mejor, verificar mejor y exigir información con mayor fundamento.

---

## 7. Inteligencia artificial y RAG

La inteligencia artificial será una interfaz de consulta asistida, no una autoridad factual.

El chatbot o agente conversacional de Open Data Jalisco deberá operar bajo un principio estricto:

> No debe responder afirmaciones sustantivas sin respaldo documental recuperado.

Cuando la información no exista en la base, sea insuficiente, esté incompleta o no pueda verificarse, el sistema debe decirlo claramente.

El asistente podrá:

- explicar documentos públicos en lenguaje claro;
- resumir contratos, actas, licitaciones o reglamentos;
- comparar documentos;
- señalar posibles inconsistencias documentales;
- indicar qué evidencia encontró;
- indicar qué evidencia no encontró;
- sugerir al usuario que consulte al municipio o realice una solicitud de información;
- mostrar documentos fuente;
- mostrar fragmentos relevantes;
- mostrar fechas, hashes y URLs oficiales.

El asistente no deberá:

- inventar fuentes;
- asumir corrupción;
- acusar personas;
- inferir delitos;
- afirmar intenciones políticas;
- ocultar incertidumbre;
- responder sin documentos;
- presentar texto generado como si fuera documento oficial;
- sustituir asesoría legal, auditoría o investigación formal.

---

## 8. Integridad de datos

Cada documento capturado deberá contar, cuando sea técnicamente posible, con:

- identificador interno;
- título;
- municipio;
- fuente;
- URL oficial;
- fecha de captura;
- tipo de archivo;
- hash SHA-256;
- ruta de almacenamiento;
- estado de procesamiento;
- versión;
- metadata de origen;
- manifest asociado.

Los documentos originales deberán almacenarse de forma inmutable o, como mínimo, bajo una política de no modificación.

Si una fuente oficial cambia un documento, el sistema deberá registrar una nueva versión en lugar de sobrescribir la anterior.

Los manifiestos públicos deberán permitir verificar qué documentos forman parte de un dataset, cuándo fueron capturados y con qué hash.

---

## 9. Gobierno open source

El software de Open Data Jalisco se publicará bajo la licencia **GNU Affero General Public License v3.0**, salvo que se indique lo contrario para componentes específicos.

La elección de AGPLv3 responde a la intención de mantener el proyecto abierto incluso cuando sea usado como servicio web. Si una persona u organización modifica el software y lo ofrece públicamente como servicio, deberá publicar también sus modificaciones bajo los términos de la licencia.

Los documentos oficiales recopilados no son propiedad del proyecto. Open Data Jalisco no se atribuye autoría sobre documentos gubernamentales, reglamentos, actas, contratos, licitaciones o archivos emitidos por autoridades públicas.

El proyecto preserva, referencia, procesa e indexa información pública con fines de consulta, trazabilidad, investigación, participación ciudadana y reutilización técnica.

---

## 10. Contribuciones

El proyecto podrá aceptar contribuciones de la comunidad mediante pull requests, issues, reportes, documentación, mejoras técnicas, nuevos scrapers, validaciones de fuentes, pruebas, corrección de errores y propuestas de arquitectura.

Sin embargo, las contribuciones no tendrán acceso directo a modificar la base oficial de producción.

Los cambios aceptables pueden incluir:

- nuevos conectores a fuentes oficiales;
- mejoras en scrapers;
- mejoras en parsers;
- mejoras en extracción de texto;
- mejoras en chunking semántico;
- mejoras en documentación;
- tests;
- reportes de errores;
- nuevas configuraciones de municipios;
- validaciones de integridad;
- mejoras de accesibilidad;
- mejoras de seguridad.

Los cambios no aceptables incluyen:

- insertar documentos no verificables como si fueran oficiales;
- modificar hashes históricos;
- alterar documentos raw;
- eliminar evidencia sin justificación;
- agregar inferencias políticas como metadata factual;
- exponer datos personales fuera de contexto;
- introducir sesgos partidistas;
- romper la trazabilidad hacia fuentes oficiales.

---

## 11. Sostenibilidad

Open Data Jalisco podrá aceptar donaciones voluntarias para cubrir costos técnicos de operación.

Las donaciones, si existen, deberán destinarse prioritariamente a:

- infraestructura;
- almacenamiento;
- dominios;
- procesamiento documental;
- OCR;
- bases de datos;
- cómputo;
- monitoreo;
- mantenimiento;
- seguridad;
- disponibilidad de la API;
- documentación pública.

Las donaciones no deberán comprometer la neutralidad del proyecto, alterar criterios de inclusión documental ni convertir el sistema en una herramienta partidista.

---

## 12. Relación con sociedad, academia, periodistas y autoridades

Open Data Jalisco busca funcionar como infraestructura de consulta pública y colaboración.

El proyecto puede ser útil para:

- ciudadanía;
- estudiantes;
- periodistas;
- investigadores;
- organizaciones civiles;
- desarrolladores;
- servidores públicos;
- áreas de transparencia;
- comunidades locales;
- proyectos académicos;
- medios de comunicación.

La relación deseada con autoridades no es de confrontación automática, sino de consulta, verificación y mejora de acceso a información pública.

Cuando se detecten errores, omisiones, documentos faltantes o inconsistencias, el proyecto deberá promover canales institucionales de aclaración, solicitudes de información y participación ciudadana.

---

## 13. Limitaciones

Open Data Jalisco puede contener errores.

Los scrapers pueden fallar.

Las fuentes oficiales pueden cambiar.

Los documentos pueden estar incompletos.

Algunos archivos pueden requerir OCR.

Algunos documentos pueden haber sido publicados con errores de origen.

El sistema puede no contar con todos los documentos existentes.

La ausencia de un documento en la base no significa necesariamente que el documento no exista.

Una inconsistencia detectada por el sistema no significa necesariamente una irregularidad legal.

Toda consulta debe entenderse como apoyo técnico para exploración documental, no como conclusión jurídica o auditoría oficial.

---

## 14. Compromiso de claridad

El proyecto se compromete a distinguir entre:

- documento oficial;
- texto extraído;
- metadata generada;
- chunk semántico;
- embedding;
- resumen generado por IA;
- interpretación del usuario;
- error de procesamiento;
- ausencia de evidencia.

Esta distinción es esencial para evitar que un resultado del sistema sea confundido con una afirmación oficial.

---

## 15. Visión a futuro

La visión de Open Data Jalisco es construir una infraestructura abierta, verificable y reutilizable para información pública municipal en Jalisco.

El proyecto comenzará con Tala, pero deberá diseñarse para crecer hacia otros municipios.

A largo plazo, el sistema podrá incluir:

- más municipios;
- más tipos documentales;
- búsqueda semántica;
- búsqueda por metadata;
- API pública;
- chatbot con RAG;
- comparación histórica;
- manifiestos descargables;
- paneles de integridad;
- reportes de documentos faltantes;
- herramientas para solicitudes de información;
- datasets reutilizables;
- colaboración con estudiantes, ciudadanía y organizaciones.

El éxito del proyecto no se medirá únicamente por tener inteligencia artificial, sino por aumentar la capacidad ciudadana de encontrar, verificar y entender información pública.

---

## 16. Frase guía

> Información pública, verificable y consultable para una ciudadanía más informada.

Open Data Jalisco no busca reemplazar a las instituciones.

Busca que la información pública sea más accesible, más trazable y más útil para la sociedad.
