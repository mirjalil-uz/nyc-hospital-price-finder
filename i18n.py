"""Spanish for the app.

The app's code is written in English. This module translates text at the point where it is
shown: `install()` wraps Streamlit's display functions so that every label, sentence, table
heading and option passes through `tr()`. Text with no translation is shown in English, so a
missing entry is never an error. Values used by the app's logic (the option a person picked,
dictionary keys) stay in English; only what is displayed changes.

Hospital names, insurer names and the service descriptions taken from hospital files are not
translated.
"""

import re

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

SPANISH = "Español"

# Whole strings.
ES = {
    # header and step 1
    "Official hospital price files": "Archivos oficiales de precios de hospitales",
    "Free to use, no sign-up": "Gratis, sin registrarse",
    "💳 Step 1: Choose your insurance": "💳 Paso 1: Elija su seguro",
    "✅ Step 1: Your insurance": "✅ Paso 1: Su seguro",
    "Prices depend on your insurance, so this comes first. Pick from the list, or tap a common choice below.":
        "Los precios dependen de su seguro, por eso esto va primero. Elija de la lista o toque una opción común.",
    "Your insurance": "Su seguro",
    "Choose your insurance provider, or say that you have none": "Elija su aseguradora, o indique que no tiene seguro",
    "I have no insurance": "No tengo seguro",
    "I don't have insurance (I will pay myself)": "No tengo seguro (pagaré por mi cuenta)",
    "My insurance is not listed": "Mi seguro no aparece en la lista",
    "Not sure (use all of this insurer's plans)": "No estoy seguro (usar todos los planes de esta aseguradora)",
    "👆 Start by choosing your insurance, so that the prices you see are the ones that apply to you.":
        "👆 Empiece por elegir su seguro, para que los precios que vea sean los que le corresponden.",
    "You will see each hospital's cash price, which is what it charges people who pay themselves.":
        "Verá el precio en efectivo de cada hospital, que es lo que cobra a quienes pagan por su cuenta.",
    "It is usually printed on your insurance card. Plans through a job are commercial; Medicare Advantage, "
    "Medicaid, Essential Plan and Child Health Plus are government programmes.":
        "Suele estar impreso en su tarjeta del seguro. Los planes del trabajo son comerciales; Medicare Advantage, "
        "Medicaid, Essential Plan y Child Health Plus son programas del gobierno.",
    "Commercial / employer": "Comercial / del empleador",
    "Marketplace (individual)": "Mercado de seguros (individual)",
    "Workers' comp / No-fault": "Compensación laboral / No-fault",
    "💳 Your plan details: used to estimate what you would pay":
        "💳 Datos de su plan: se usan para estimar lo que usted pagaría",
    "Deductible left to meet ($)": "Deducible que le falta por cubrir ($)",
    "Coinsurance (%)": "Coseguro (%)",
    "Copay ($)": "Copago ($)",
    "The amount you still have to pay this year before your plan starts paying.":
        "Lo que aún debe pagar este año antes de que su plan empiece a pagar.",
    "Your share of the price after the deductible. 20% is common.":
        "Su parte del precio después del deducible. El 20% es común.",
    "A fixed fee your plan charges for the visit, if any.": "Una tarifa fija que su plan cobra por la visita, si la hay.",
    "These numbers are on your insurance card or plan summary. Leave them as they are if you are not sure. ":
        "Estos números están en su tarjeta del seguro o en el resumen del plan. Déjelos como están si no está seguro. ",
    "These numbers are on your insurance card or plan summary. Leave them as they are if you are not sure. "
    "Because your insurer is not in the list, you will see cash prices and every insurer's prices; open a hospital "
    "to look for your plan by name and enter its price by hand.":
        "Estos números están en su tarjeta del seguro o en el resumen del plan. Déjelos como están si no está seguro. "
        "Como su aseguradora no está en la lista, verá los precios en efectivo y los de todas las aseguradoras; abra "
        "un hospital para buscar su plan por nombre e ingresar su precio a mano.",
    # step 2
    "Step 2: Search for your care": "Paso 2: Busque la atención que necesita",
    "What care are you looking for?": "¿Qué atención busca?",
    "🔍  Try: broken arm, pregnancy scan, MRI brain, blood test, or a billing code like 80053":
        "🔍  Pruebe: brazo roto, ecografía de embarazo, resonancia, análisis de sangre, o un código como 80053",
    "**Popular services**": "**Servicios más buscados**",
    "**Common visits: several services added together**": "**Visitas comunes: varios servicios sumados**",
    "MRI of the brain": "Resonancia magnética del cerebro",
    "Chest X-ray": "Radiografía de tórax",
    "CT scan of the abdomen": "Tomografía del abdomen",
    "MRI of the knee": "Resonancia magnética de la rodilla",
    "Blood test: metabolic panel": "Análisis de sangre: panel metabólico",
    "Complete blood count": "Hemograma completo",
    "Heart tracing (EKG)": "Electrocardiograma (EKG)",
    "Screening mammogram": "Mamografía de detección",
    "Emergency room visit": "Visita a la sala de emergencias",
    "Colonoscopy": "Colonoscopia",
    "Vaginal delivery": "Parto vaginal",
    "Knee or hip replacement": "Reemplazo de rodilla o cadera",
    "Routine blood work": "Análisis de sangre de rutina",
    "Emergency visit for a possible broken arm": "Emergencia por posible brazo roto",
    "Emergency visit for chest pain": "Emergencia por dolor en el pecho",
    "Colonoscopy with biopsy": "Colonoscopia con biopsia",
    "Diabetes check-up": "Control de diabetes",
    "Prenatal visit with ultrasound": "Visita prenatal con ecografía",
    "A blood draw with the four most common lab panels":
        "Una extracción de sangre con los cuatro paneles de laboratorio más comunes",
    "An emergency room visit with an arm X-ray": "Una visita a emergencias con radiografía del brazo",
    "An emergency room visit with a chest X-ray and a heart tracing":
        "Una visita a emergencias con radiografía de tórax y electrocardiograma",
    "A colonoscopy where a sample is taken and examined in the lab":
        "Una colonoscopia en la que se toma una muestra y se examina en el laboratorio",
    "An office visit with a blood draw, an A1c test and a metabolic panel":
        "Una consulta con extracción de sangre, prueba A1c y panel metabólico",
    "An office visit with a pregnancy ultrasound": "Una consulta con ecografía de embarazo",
    "No service matches that search. Try fewer or different words.":
        "Ningún servicio coincide con esa búsqueda. Pruebe con menos palabras o con otras.",
    "👆 Search above or tap a popular service to compare prices across the city.":
        "👆 Busque arriba o toque un servicio para comparar precios en toda la ciudad.",
    # home page
    "Hospitals": "Hospitales",
    "Insurance prices": "Precios de seguros",
    "Services to search": "Servicios para buscar",
    "Boroughs covered": "Distritos cubiertos",
    "All 5": "Los 5",
    "🧭 How it works": "🧭 Cómo funciona",
    "**1. Choose your insurance, then search**": "**1. Elija su seguro y luego busque**",
    "**2. Compare hospitals**": "**2. Compare hospitales**",
    "**3. Call or get directions**": "**3. Llame o vea cómo llegar**",
    "Pick your insurance provider, then type what you need in everyday words, such as a broken arm or a blood test, "
    "or tap a popular service.":
        "Elija su aseguradora y escriba lo que necesita con palabras de todos los días, como brazo roto o análisis "
        "de sangre, o toque un servicio.",
    "See the full price, what your insurance pays and what you pay, with patient ratings and distance, in a list, "
    "on a chart or on a map.":
        "Vea el precio completo, lo que paga su seguro y lo que paga usted, con calificaciones de pacientes y "
        "distancia, en una lista, un gráfico o un mapa.",
    "Open any hospital for its phone number, address and directions before you go.":
        "Abra cualquier hospital para ver su teléfono, dirección y cómo llegar antes de ir.",
    "Hospitals in the United States must publish their prices, but the files are huge and hard to read. This app "
    "loads the official file from each New York City hospital and puts the prices side by side.":
        "Los hospitales de Estados Unidos deben publicar sus precios, pero los archivos son enormes y difíciles de "
        "leer. Esta aplicación carga el archivo oficial de cada hospital de la ciudad de Nueva York y pone los "
        "precios lado a lado.",
    "❓ Frequently asked questions": "❓ Preguntas frecuentes",
    # filters
    "Type of visit": "Tipo de visita",
    "Any type of visit": "Cualquier tipo de visita",
    "Outpatient (no overnight stay)": "Ambulatoria (sin pasar la noche)",
    "Inpatient (admitted to hospital)": "Hospitalización (ingreso al hospital)",
    "Borough": "Distrito",
    "All boroughs": "Todos los distritos",
    "Your ZIP code (optional)": "Su código postal (opcional)",
    "For example 11226": "Por ejemplo 11226",
    "That ZIP code is not in the New York area list.": "Ese código postal no está en la lista del área de Nueva York.",
    "Distance": "Distancia",
    "Any distance": "Cualquier distancia",
    "Within 2 miles": "A menos de 2 millas",
    "Within 5 miles": "A menos de 5 millas",
    "Within 10 miles": "A menos de 10 millas",
    "Enter your ZIP code to filter by distance.": "Ingrese su código postal para filtrar por distancia.",
    "Patient rating": "Calificación de pacientes",
    "Any rating": "Cualquier calificación",
    "2 stars or more": "2 estrellas o más",
    "3 stars or more": "3 estrellas o más",
    "4 stars or more": "4 estrellas o más",
    "Highest cash price ($, optional)": "Precio máximo en efectivo ($, opcional)",
    "Any price": "Cualquier precio",
    "No hospital publishes a price for this service with these filters. Try a different type of visit.":
        "Ningún hospital publica un precio para este servicio con estos filtros. Pruebe otro tipo de visita.",
    "No hospital publishes a price for every part of this with these filters. Try a different type of visit.":
        "Ningún hospital publica un precio para todas las partes con estos filtros. Pruebe otro tipo de visita.",
    # results
    "Hospitals with a price": "Hospitales con precio",
    "Lowest cash price": "Precio en efectivo más bajo",
    "Highest cash price": "Precio en efectivo más alto",
    "⭐ Highest patient rating": "⭐ Mejor calificación de pacientes",
    "💵 Lowest cash price": "💵 Precio en efectivo más bajo",
    "⚖️ Best value (3+ stars, lowest price)": "⚖️ Mejor relación (3+ estrellas, menor precio)",
    "See details": "Ver detalles",
    "All hospitals for this service": "Todos los hospitales para este servicio",
    "Sort hospitals by": "Ordenar hospitales por",
    "Patient rating (highest first)": "Calificación de pacientes (mayor primero)",
    "Cash price (lowest first)": "Precio en efectivo (menor primero)",
    "Typical insurer price (lowest first)": "Precio típico del seguro (menor primero)",
    "What you pay (lowest first)": "Lo que usted paga (menor primero)",
    "Closest first": "Más cercano primero",
    "Group campuses that share one price list": "Agrupar sedes que comparten una lista de precios",
    "Hospitals in one system often publish a single price file, so their prices are identical. Grouping shows them "
    "as one row.":
        "Los hospitales de un mismo sistema suelen publicar un solo archivo, por lo que sus precios son idénticos. "
        "Al agrupar se muestran en una sola fila.",
    "📋 All hospitals": "📋 Todos los hospitales",
    "📊 Price chart": "📊 Gráfico de precios",
    "🗺️ Map": "🗺️ Mapa",
    "Click a hospital's row to see its address, directions and full price detail.":
        "Haga clic en la fila de un hospital para ver su dirección, cómo llegar y el detalle de precios.",
    "View hospital": "Ver hospital",
    "Hover over a bar for details. Hospitals that publish no cash price are left out.":
        "Pase el cursor sobre una barra para ver detalles. No se incluyen hospitales sin precio en efectivo.",
    "No hospital publishes a cash price for this service.":
        "Ningún hospital publica un precio en efectivo para este servicio.",
    "Each dot is a hospital with a price for this service. Click a dot to open its details; the orange dot is the "
    "hospital shown below.":
        "Cada punto es un hospital con precio para este servicio. Haga clic en un punto para ver sus detalles; el "
        "punto naranja es el hospital que se muestra abajo.",
    "Published cash price": "Precio en efectivo publicado",
    # the recommendation
    "🏆 Your best option": "🏆 Su mejor opción",
    "Your cost (estimate)": "Su costo (estimado)",
    "Cash price here": "Precio en efectivo aquí",
    "Patients say": "Opinión de pacientes",
    "How far": "Distancia",
    "**Why this one**": "**Por qué esta opción**",
    "🧭 Get directions": "🧭 Cómo llegar",
    "**Two other good options**": "**Otras dos buenas opciones**",
    "**Another good option**": "**Otra buena opción**",
    "🥈 Second choice": "🥈 Segunda opción",
    "🥉 Third choice": "🥉 Tercera opción",
    "**The numbers behind it**": "**Las cifras detrás**",
    "📝 Questions to ask the hospital before you go": "📝 Preguntas para hacer al hospital antes de ir",
    "- Is this the total price, or will there be separate bills, such as a doctor's fee?\n"
    "- Are you in my insurance plan's network for this service?\n"
    "- What will I owe on the day, and can I pay in instalments?\n"
    "- If I pay myself, is there a discount or financial assistance I can apply for?\n"
    "- Do I need a referral or prior approval from my insurer?":
        "- ¿Es este el precio total, o habrá facturas aparte, como los honorarios del médico?\n"
        "- ¿Están en la red de mi plan de seguro para este servicio?\n"
        "- ¿Cuánto deberé pagar ese día, y puedo pagar en cuotas?\n"
        "- Si pago por mi cuenta, ¿hay algún descuento o ayuda financiera que pueda solicitar?\n"
        "- ¿Necesito una remisión o autorización previa de mi aseguradora?",
    "- Medicare has no patient rating for it": "- Medicare no tiene calificación de pacientes para este hospital",
    "not rated": "sin calificación",
    # table headings
    "Hospital": "Hospital",
    "Would recommend": "Lo recomendarían",
    "Phone": "Teléfono",
    "Cash price (no insurance)": "Precio en efectivo (sin seguro)",
    "Insurer prices (all plans)": "Precios de seguros (todos los planes)",
    "Typical insurer price": "Precio típico del seguro",
    "List price": "Precio de lista",
    "Prices as of": "Precios al",
    "Covered?": "¿Cubierto?",
    "Full price": "Precio completo",
    "Insurance pays (estimate)": "El seguro paga (estimado)",
    "You pay (estimate)": "Usted paga (estimado)",
    "Service": "Servicio",
    "Billing code": "Código de facturación",
    "Cash price": "Precio en efectivo",
    "Insurer price": "Precio del seguro",
    "Insurer": "Aseguradora",
    "Plan": "Plan",
    "Kind of plan": "Tipo de plan",
    "Setting": "Modalidad",
    "Modifiers": "Modificadores",
    "Price": "Precio",
    "Method": "Método",
    "Other payment terms": "Otras condiciones de pago",
    # one hospital
    "Step 4: Hospital details": "Paso 4: Detalles del hospital",
    "Patient rating: not rated": "Calificación de pacientes: sin calificación",
    "🧭 Get directions on Google Maps": "🧭 Cómo llegar en Google Maps",
    "A price here is under a tenth of what other hospitals publish for this service. That usually means a mistake "
    "in the hospital's file or a line for something smaller. Call to confirm it.":
        "Un precio aquí es menos de una décima parte de lo que publican otros hospitales para este servicio. Suele "
        "ser un error en el archivo del hospital o una línea para algo menor. Llame para confirmarlo.",
    "Insurance pays about": "El seguro paga aproximadamente",
    "You pay about": "Usted paga aproximadamente",
    "**Other prices here**": "**Otros precios aquí**",
    "If you pay yourself": "Si paga por su cuenta",
    "⚠️ This hospital lists very different cash prices under this billing code. The lower one may cover only part "
    "of the service. Ask the hospital which price applies to you.":
        "⚠️ Este hospital publica precios en efectivo muy distintos con este código. El más bajo puede cubrir solo "
        "una parte del servicio. Pregunte al hospital qué precio le corresponde.",
    "🔗 To share this comparison, copy the address from your browser's address bar.":
        "🔗 Para compartir esta comparación, copie la dirección de la barra de su navegador.",
    "🧮 Try a different plan price": "🧮 Pruebe con otro precio de plan",
    "Your plan's price ($)": "Precio de su plan ($)",
    "Starts at the typical insurer price here. Replace it with your own plan's price from the table below.":
        "Empieza con el precio típico del seguro aquí. Cámbielo por el precio de su plan según la tabla de abajo.",
    "Deductible left": "Deducible pendiente",
    "Coinsurance": "Coseguro",
    "Copay": "Copago",
    "You might owe about": "Podría deber aproximadamente",
    "The deductible, coinsurance and copay come from your plan details in step 1. A rough guide only. It does not "
    "know your out-of-pocket maximum, whether this hospital is in your network, or what other services your visit "
    "will include. Confirm with your insurer and the hospital.":
        "El deducible, el coseguro y el copago vienen de los datos de su plan en el paso 1. Es solo una guía "
        "aproximada. No conoce su gasto máximo anual, si este hospital está en su red ni qué otros servicios "
        "incluirá su visita. Confirme con su aseguradora y con el hospital.",
    "**What the total is made of**": "**De qué se compone el total**",
    "Search for one of these services by name to see every insurance plan's price for it. A real visit can include "
    "other charges, such as a doctor's fee.":
        "Busque uno de estos servicios por nombre para ver el precio de cada plan. Una visita real puede incluir "
        "otros cargos, como los honorarios del médico.",
    "🗂️ Where does the data come from?": "🗂️ ¿De dónde vienen los datos?",
    "These are published prices, not a quote. What you pay depends on your plan, your deductible and the care you "
    "receive, and a doctor's fee may be billed separately. Hospitals in the same system often share one price "
    "file, so their prices match. This app is not medical or financial advice.":
        "Estos son precios publicados, no un presupuesto. Lo que usted paga depende de su plan, su deducible y la "
        "atención que reciba, y los honorarios del médico pueden facturarse aparte. Los hospitales de un mismo "
        "sistema suelen compartir un archivo, por lo que sus precios coinciden. Esta aplicación no es asesoría "
        "médica ni financiera.",
}

# Sentences with changing parts. "{name}" in the English text matches anything, and the same
# name in the Spanish text is filled with what it matched.
TEMPLATES = [
    ("What kind of {payer} plan do you have?", "¿Qué tipo de plan de {payer} tiene?"),
    ("💳 Your {payer} plan details: used to estimate what you would pay",
     "💳 Datos de su plan de {payer}: se usan para estimar lo que usted pagaría"),
    ("{n} matching services", "{n} servicios encontrados"),
    ("Step 3: Compare hospitals  ·  Billing code: {code}  ·  Insurance: {ins}",
     "Paso 3: Compare hospitales  ·  Código: {code}  ·  Seguro: {ins}"),
    ("Step 3: Compare hospitals  ·  Package of {n} billing codes  ·  Insurance: {ins}",
     "Paso 3: Compare hospitales  ·  Paquete de {n} códigos  ·  Seguro: {ins}"),
    ("{about}. Prices are the total of: {parts}.", "{about}. Los precios son el total de: {parts}."),
    ("None of the {n} hospitals with a price for this service match the distance, rating and price filters. "
     "Loosen one of them to see results.",
     "Ninguno de los {n} hospitales con precio para este servicio cumple los filtros de distancia, calificación y "
     "precio. Relaje alguno para ver resultados."),
    ("💡 The same service costs from **{a}** to **{b}** depending on the hospital, a difference of **{c}** "
     "({t} times more).",
     "💡 El mismo servicio cuesta entre **{a}** y **{b}** según el hospital, una diferencia de **{c}** "
     "({t} veces más)."),
    ("💡 The same service costs from **{a}** to **{b}** depending on the hospital, a difference of **{c}**.",
     "💡 El mismo servicio cuesta entre **{a}** y **{b}** según el hospital, una diferencia de **{c}**."),
    ("⚠️ {n} hospitals show prices under a tenth of what the others publish. Such a price is usually a filing "
     "mistake, so it is marked in the list and left out of the figures and suggestions here.",
     "⚠️ {n} hospitales muestran precios de menos de una décima parte de lo que publican los demás. Suele ser un "
     "error de registro, por eso se marca en la lista y no se usa en las cifras ni en las sugerencias."),
    ("⚠️ {n} hospital shows a price under a tenth of what the others publish. Such a price is usually a filing "
     "mistake, so it is marked in the list and left out of the figures and suggestions here.",
     "⚠️ {n} hospital muestra un precio de menos de una décima parte de lo que publican los demás. Suele ser un "
     "error de registro, por eso se marca en la lista y no se usa en las cifras ni en las sugerencias."),
    ("⚠️ {n} hospitals list very different prices under this one billing code. They are compared on their higher "
     "price, because the low line often covers only part of the service, such as the doctor's fee.",
     "⚠️ {n} hospitales publican precios muy distintos con este mismo código. Se comparan por su precio más alto, "
     "porque la línea baja suele cubrir solo una parte del servicio, como los honorarios del médico."),
    ("⚠️ {n} hospital lists very different prices under this one billing code. They are compared on their higher "
     "price, because the low line often covers only part of the service, such as the doctor's fee.",
     "⚠️ {n} hospital publica precios muy distintos con este mismo código. Se compara por su precio más alto, "
     "porque la línea baja suele cubrir solo una parte del servicio, como los honorarios del médico."),
    ("📞 Call {phone}", "📞 Llamar al {phone}"),
    ("{stars}  {n}% recommend", "{stars}  {n}% lo recomiendan"),
    ("{n} miles", "{n} millas"),
    ("- What you would pay is the lowest of the {n} hospitals compared: {x}",
     "- Lo que usted pagaría es lo más bajo de los {n} hospitales comparados: {x}"),
    ("- The cash price is the lowest of the {n} hospitals compared: {x}",
     "- El precio en efectivo es el más bajo de los {n} hospitales comparados: {x}"),
    ("- What you would pay is {x} below the middle of the hospitals compared",
     "- Lo que usted pagaría está {x} por debajo del precio medio de los hospitales comparados"),
    ("- The cash price is {x} below the middle of the hospitals compared",
     "- El precio en efectivo está {x} por debajo del precio medio de los hospitales comparados"),
    ("- What you would pay is {x}, close to or above the middle ({m})",
     "- Lo que usted pagaría es {x}, cerca o por encima del precio medio ({m})"),
    ("- The cash price is {x}, close to or above the middle ({m})",
     "- El precio en efectivo es {x}, cerca o por encima del precio medio ({m})"),
    ("- Patients rate it {n} of 5 stars, and {p}% would definitely recommend it",
     "- Los pacientes le dan {n} de 5 estrellas, y el {p}% lo recomendaría sin duda"),
    ("- It is about {m} miles from you", "- Está a unas {m} millas de usted"),
    ("### You pay about {x}", "### Usted paga aprox. {x}"),
    ("### Cash price {x}", "### Precio en efectivo {x}"),
    ("Chosen by weighing cost first, then patient rating, then distance. {rest}Children's, psychiatric, cancer "
     "and long-term care hospitals are not suggested automatically. It is a suggestion to start from, not medical "
     "advice.",
     "Elegido dando más peso al costo, luego a la calificación de pacientes y luego a la distancia. {rest}Los "
     "hospitales infantiles, psiquiátricos, oncológicos y de cuidados prolongados no se sugieren automáticamente. "
     "Es una sugerencia para empezar, no un consejo médico."),
    ("Chosen by weighing cost first, then patient rating. Enter your ZIP code above to take distance into account. "
     "{rest}Children's, psychiatric, cancer and long-term care hospitals are not suggested automatically. It is a "
     "suggestion to start from, not medical advice.",
     "Elegido dando más peso al costo y luego a la calificación de pacientes. Ingrese su código postal arriba para "
     "tener en cuenta la distancia. {rest}Los hospitales infantiles, psiquiátricos, oncológicos y de cuidados "
     "prolongados no se sugieren automáticamente. Es una sugerencia para empezar, no un consejo médico."),
    ("💳 Lowest cost with {payer}", "💳 Menor costo con {payer}"),
    ("### {n}% recommend", "### {n}% lo recomiendan"),
    ("### You pay about {x}", "### Usted paga aprox. {x}"),
    ("Full price: **{a}** · {payer} pays about **{b}** · You pay about **{c}**",
     "Precio completo: **{a}** · {payer} paga aprox. **{b}** · Usted paga aprox. **{c}**"),
    ("No {payer} price listed. Cash price: **{a}**", "Sin precio de {payer}. Precio en efectivo: **{a}**"),
    ("Cash price: **{a}** · Typical insurer price: **{b}**",
     "Precio en efectivo: **{a}** · Precio típico del seguro: **{b}**"),
    ("Showing the first {n} of {m}. Change the sort or filters to see others.",
     "Se muestran los primeros {n} de {m}. Cambie el orden o los filtros para ver otros."),
    ("{n} hospitals with no published price for this service", "{n} hospitales sin precio publicado para este servicio"),
    ("Price file not loaded yet: {names}", "Archivo de precios aún no cargado: {names}"),
    ("These prices are from {date}, more than a year ago. Call the hospital to check that they still apply.",
     "Estos precios son de {date}, hace más de un año. Llame al hospital para confirmar que siguen vigentes."),
    ("Patient rating: {stars} ({n} of 5), {p}% would definitely recommend, from {s} patient surveys",
     "Calificación de pacientes: {stars} ({n} de 5), {p}% lo recomendaría sin duda, según {s} encuestas"),
    ("Medicare overall quality: {stars} ({n} of 5)", "Calidad general según Medicare: {stars} ({n} de 5)"),
    ("Rated by Medicare as part of {name}.", "Calificado por Medicare como parte de {name}."),
    ("🚗 About {m} miles from ZIP code {z}, in a straight line",
     "🚗 A unas {m} millas del código postal {z}, en línea recta"),
    ("📞 {link} (main line)", "📞 {link} (línea principal)"),
    ("**With {payer}**", "**Con {payer}**"),
    ("{payer} has agreed a price of **{a}** for this service here. With {d} of deductible left, {c}% coinsurance "
     "and {k} copay, your share is about **{y}**.",
     "{payer} ha acordado un precio de **{a}** por este servicio aquí. Con {d} de deducible pendiente, {c}% de "
     "coseguro y {k} de copago, su parte es de aproximadamente **{y}**."),
    ("This hospital's price file lists no fixed {payer} price for this service. It may be out of network for your "
     "plan, or the plan may pay by a formula. If it is not covered, you would pay the cash price, about {y}. Call "
     "the hospital and your insurer to check.",
     "El archivo de este hospital no incluye un precio fijo de {payer} para este servicio. Puede estar fuera de la "
     "red de su plan, o el plan puede pagar según una fórmula. Si no está cubierto, usted pagaría el precio en "
     "efectivo, unos {y}. Llame al hospital y a su aseguradora para confirmarlo."),
    ("Typical {payer} price", "Precio típico de {payer}"),
    ("The cash price here is **{a} below** the middle cash price of the hospitals listed ({b}).",
     "El precio en efectivo aquí está **{a} por debajo** del precio medio de los hospitales de la lista ({b})."),
    ("The cash price here is **{a} above** the middle cash price of the hospitals listed ({b}).",
     "El precio en efectivo aquí está **{a} por encima** del precio medio de los hospitales de la lista ({b})."),
    ("Prices from the hospital's file dated {d}.", "Precios del archivo del hospital con fecha {d}."),
    ("That is {a} toward your deductible, {b} coinsurance and {c} copay. Your plan would pay about {d}.",
     "Son {a} para su deducible, {b} de coseguro y {c} de copago. Su plan pagaría aproximadamente {d}."),
    ("The cash price here is {a}, lower than this estimate. Ask the hospital whether you can pay the cash price "
     "instead of using insurance.",
     "El precio en efectivo aquí es {a}, menor que esta estimación. Pregunte al hospital si puede pagar el precio "
     "en efectivo en lugar de usar el seguro."),
    ("Prices by insurance plan ({n} rows)", "Precios por plan de seguro ({n} filas)"),
    ("{pre}A blank price means the plan pays by a percentage or a formula instead of a fixed amount; the last "
     "column gives those terms. Drag a column edge to widen it, or use the full-screen button at the top right of "
     "the table.",
     "{pre}Un precio en blanco significa que el plan paga por porcentaje o fórmula en vez de un monto fijo; la "
     "última columna da esas condiciones. Arrastre el borde de una columna para ensancharla, o use el botón de "
     "pantalla completa arriba a la derecha de la tabla."),
    ("**Payment terms in full ({n})**", "**Condiciones de pago completas ({n})**"),
    ("Lines in the hospital's price file for {code}", "Líneas del archivo de precios del hospital para {code}"),
]

# Very short patterns. They are tried last and only on short text, because a pattern as loose as
# "A of B" would otherwise swallow whole sentences that have their own translation above.
SHORT = [
    (re.compile(r"(\d[\d,]*) of (\d[\d,]*)"), r"\1 de \2"),
    (re.compile(r"(\d+) million"), r"\1 millones"),
    (re.compile(r"(.+) agreed price"), r"Precio acordado con \1"),
    (re.compile(r"(.+) price"), r"Precio de \1"),
]

# Short pieces that appear inside table cells next to numbers.
FRAGMENTS = [
    ("not published", "no publicado"),
    ("not rated", "sin calificación"),
    ("unusually low", "inusualmente bajo"),
    ("(cash price)", "(precio en efectivo)"),
    ("(old)", "(antiguo)"),
    ("none listed", "no figura"),
    ("of patients", "de los pacientes"),
    ("more with the same prices", "más con los mismos precios"),
    ("price listed", "con precio"),
    ("Yes, ", "Sí, "),
]
# Table columns whose text comes from hospitals' files and is shown as published.
AS_PUBLISHED = {"insurer", "plan", "details", "description", "hospital", "address", "system", "source_url"}


def _compile(template):
    pattern = re.escape(template)
    pattern = re.sub(r"\\\{(\w+)\\\}", r"(?P<\1>.*?)", pattern)
    return re.compile(pattern, re.DOTALL)


_COMPILED = [(_compile(english), spanish) for english, spanish in TEMPLATES]


def spanish_on():
    return st.session_state.get("lang") == SPANISH


def tr(text):
    """The Spanish for `text` when Spanish is selected and a translation exists; otherwise `text` itself."""
    if not isinstance(text, str) or not spanish_on():
        return text
    if text in ES:
        return ES[text]
    for pattern, spanish in _COMPILED:
        match = pattern.fullmatch(text)
        if match:
            # A captured part may itself be a known phrase, such as a service name.
            return spanish.format(**{name: ES.get(value, value) for name, value in match.groupdict().items()})
    if len(text) < 60:
        for pattern, spanish in SHORT:
            if pattern.fullmatch(text):
                return pattern.sub(spanish, text)
    return text


def tr_cell(value):
    if not isinstance(value, str) or not value:
        return value
    for english, spanish in FRAGMENTS:
        value = value.replace(english, spanish)
    return value


def tr_table(data):
    """A copy of a table with translated headings and the short English phrases in its cells translated."""
    if not isinstance(data, pd.DataFrame) or not spanish_on():
        return data
    out = data.copy()
    for column in out.columns:
        if column not in AS_PUBLISHED and out[column].dtype == object or str(out[column].dtype).startswith("str"):
            if column not in AS_PUBLISHED:
                out[column] = out[column].map(tr_cell)
    return out.rename(columns={c: tr(c) for c in out.columns})


TEXT_KEYWORDS = ("label", "body", "placeholder", "help", "delta")
TEXT_METHODS = ("markdown", "caption", "subheader", "header", "info", "warning", "success", "error", "button",
                "link_button", "expander", "toggle", "text_input", "number_input")
CHOICE_METHODS = ("selectbox", "radio", "multiselect")


def _translate_keywords(kwargs):
    for name in TEXT_KEYWORDS:
        if isinstance(kwargs.get(name), str):
            kwargs[name] = tr(kwargs[name])


def _wrap_text(original):
    def wrapped(self, *args, **kwargs):
        if args and isinstance(args[0], str):
            args = (tr(args[0]), *args[1:])
        _translate_keywords(kwargs)
        return original(self, *args, **kwargs)
    return wrapped


def _wrap_choice(original):
    def wrapped(self, *args, **kwargs):
        if args and isinstance(args[0], str):
            args = (tr(args[0]), *args[1:])
        _translate_keywords(kwargs)
        kwargs.setdefault("format_func", tr)  # show options in Spanish, keep their English values
        return original(self, *args, **kwargs)
    return wrapped


def _wrap_write(original):
    def wrapped(self, *args, **kwargs):
        return original(self, *(tr(a) if isinstance(a, str) else a for a in args), **kwargs)
    return wrapped


def _wrap_metric(original):
    def wrapped(self, label, value, delta=None, **kwargs):
        return original(self, tr(label), tr(value), tr(delta), **kwargs)
    return wrapped


def _wrap_tabs(original):
    def wrapped(self, tabs, *args, **kwargs):
        return original(self, [tr(t) for t in tabs], *args, **kwargs)
    return wrapped


def _wrap_dataframe(original):
    def wrapped(self, data=None, *args, **kwargs):
        if spanish_on() and isinstance(kwargs.get("column_config"), dict):
            kwargs["column_config"] = {tr(k): v for k, v in kwargs["column_config"].items()}
        return original(self, tr_table(data), *args, **kwargs)
    return wrapped


def install():
    """Route Streamlit's display functions through the translator. Safe to call on every rerun."""
    if getattr(DeltaGenerator, "_spanish_installed", False):
        return
    wrappers = {name: _wrap_text for name in TEXT_METHODS}
    wrappers.update({name: _wrap_choice for name in CHOICE_METHODS})
    wrappers.update(write=_wrap_write, metric=_wrap_metric, tabs=_wrap_tabs, dataframe=_wrap_dataframe)
    for name, wrap in wrappers.items():
        setattr(DeltaGenerator, name, wrap(getattr(DeltaGenerator, name)))
        # `st.write` and friends were bound to the old methods when Streamlit was imported.
        setattr(st, name, getattr(st._main, name))
    DeltaGenerator._spanish_installed = True
