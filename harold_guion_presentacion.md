# HAROLD - DOCUMENTO PARA MARTIN

Este documento esta pensado como apoyo para montar la presentacion de la parte de Harold.

La idea no es soltar teoria tecnica, sino explicar de forma clara:

- para que sirve la app de escritorio
- como sigue un flujo real de trabajo
- por que esta bien organizada por dentro

El tono debe ser natural, facil de entender y visual, como en el ejemplo que me has pasado.

---

## Diapositiva 1

Para nuestra parte del TFG, lo que hemos desarrollado es una aplicacion de escritorio de facturacion. La elegimos asi porque queriamos una herramienta comoda de usar, estable y pensada para trabajar de verdad con ella, no solo para enseñarla unos minutos y ya esta.

La aplicacion esta hecha con **Python** y **PySide6**. Python nos ha venido muy bien porque nos ha permitido construir toda la logica de la aplicacion de una forma clara y bastante ordenada. Y PySide6 es lo que nos ha permitido darle forma visual, es decir, convertir esa logica en una aplicacion de escritorio real, con ventanas, botones, paneles y pantallas de gestion.

La forma mas sencilla de entender esta diapositiva es imaginar que la aplicacion es como una **mesa de trabajo central**. En esa mesa no tienes papeles sueltos ni cosas desperdigadas. Lo tienes todo en el mismo sitio y en el orden correcto.

Primero trabajas con los **clientes**, despues con los **productos o servicios**, luego generas las **facturas** y por ultimo puedes **exportarlas** o seguir su estado.

Es decir, no hemos hecho una app que solo guarda datos. Hemos hecho una app que te lleva de la mano durante todo el proceso de facturacion.

### Imagen para esta diapositiva
- Captura general de la aplicacion o del dashboard

### Flujo visual que deberia representar la diapositiva
`Clientes -> Productos/Servicios -> Facturas -> Exportacion`

---

## Diapositiva 2

Si bajamos al uso practico, la aplicacion funciona como una cadena de trabajo bastante natural.

Primero se registran o consultan los **clientes**, porque son la base de todo. Si no tienes bien guardados sus datos fiscales, su contacto o su informacion principal, no puedes facturar de forma correcta.

Despues entra en juego el apartado de **productos y servicios**. Esto nos sirve como si fuera una especie de **catalogo interno**. En vez de escribir cada vez lo mismo desde cero, ya tenemos guardados los conceptos, sus precios y sus categorias. Eso ahorra tiempo y, sobre todo, evita errores tontos por repetir informacion manualmente.

Y con esas dos piezas ya preparadas, llegamos al bloque de **facturas**. Aqui es donde la aplicacion junta todo y construye el documento final.

Una buena forma de entenderlo es pensar que esto funciona como preparar un pedido:

- el cliente seria para quien va el pedido
- los productos o servicios serian lo que vas a incluir
- y la factura seria el recibo final bien montado

Ademas, la factura no se queda congelada como un archivo muerto. Puede ir pasando por distintos estados, como **borrador**, **emitida**, **pagada** o **cancelada**. Eso hace que la app no solo sirva para crear facturas, sino tambien para seguir su recorrido y saber en que punto esta cada una.

### Imagen para esta diapositiva
- Captura de la vista de Clientes
- Captura de la vista de Productos/Servicios
- Captura de la vista de Facturas

### Flujo visual que deberia representar la diapositiva
- Clientes
- Productos/Servicios
- Facturas

O en formato cadena:

`Registrar cliente -> Reutilizar catalogo -> Generar factura -> Controlar estado`

---

## Diapositiva 3

Por fuera, la aplicacion se ve sencilla. Y eso es buena señal, porque significa que al usuario no le estorbamos con complicaciones. Pero por dentro esta organizada de manera que se pueda mantener y ampliar sin tener que rehacerlo todo.

Para explicarlo de forma facil, podemos imaginar la aplicacion como una **oficina bien organizada**.

La **interfaz** es la parte que ve el usuario. Seria como el **mostrador** o la **mesa de atencion**. Es donde pulsas botones, consultas informacion y te mueves por las pantallas.

Los **controladores** actuan como quien recibe lo que pide el usuario y lo dirige al sitio correcto. Serian como la persona que escucha lo que necesitas y se encarga de mover la peticion.

Los **servicios** son los que realmente hacen el trabajo importante por dentro. Son los que procesan la informacion, calculan, validan y aplican la logica de negocio. Si seguimos con la metafora, serian como el personal de administracion que esta detras resolviendo las tareas de verdad.

Y los **datos** son el archivador. El sitio donde se guarda todo lo necesario para que luego pueda recuperarse bien y sin desorden.

Gracias a esta separacion, la aplicacion no esta montada como un bloque unico y caotico. Esta dividida por capas, y eso hace que sea mucho mas facil corregir cosas, añadir funciones nuevas o probar que todo funciona como debe.

Tambien contamos con **tests**, que son como una revision antes de entregar un documento importante. Nos sirven para comprobar que ciertas partes criticas del sistema siguen funcionando correctamente.

En resumen, no es solo una app que se ve bien. Es una app que esta construida con cabeza.

### Imagen para esta diapositiva
- Captura del arbol del proyecto
- Si se puede, que se vean carpetas como:
  - `views`
  - `controllers`
  - `services`
  - `models`
  - `tests`

### Flujo visual que deberia representar la diapositiva
`Interfaz -> Controladores -> Servicios -> Datos`

Como apoyo visual, puede aparecer al lado una captura del arbol del proyecto para que se vea que esa separacion existe de verdad.

---

## Frase de apertura recomendada

Yo voy a explicar la parte de la aplicacion de escritorio, pero no tanto desde la teoria, sino desde como funciona realmente y como organiza todo el proceso de facturacion.

## Frase de cierre recomendada

En resumen, nuestra aportacion ha sido construir una aplicacion de escritorio que no solo permite facturar, sino que organiza un flujo de trabajo real y lo hace sobre una base que esta preparada para mantenerse y crecer.

---

## Resumen rapido para Martin

### Slide 1
- Presentar la app como herramienta completa
- Explicar tecnologias sin tecnicismos pesados
- Mostrar el flujo general

### Slide 2
- Explicar el uso real paso a paso
- Apoyarse en capturas de Clientes, Productos y Facturas
- Reforzar la idea de flujo natural

### Slide 3
- Explicar la arquitectura con una metafora sencilla
- Mostrar que no es una demo improvisada
- Cerrar con la idea de aplicacion mantenible
