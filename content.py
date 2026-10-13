"""Words for the app: everyday search terms and the frequently asked questions."""

# Everyday words -> the billing codes hospitals file that care under.
# Each entry: (plain name, words or phrases that should find it, [(code type, code), ...]).
EVERYDAY = [
    ("Pregnancy ultrasound", ["pregnan", "prenatal", "baby scan", "fetal", "sonogram"],
     [("CPT/HCPCS", "76805"), ("CPT/HCPCS", "76801")]),
    ("Giving birth: vaginal delivery", ["birth", "deliver", "labor", "having a baby"], [("MS-DRG", "807")]),
    ("Giving birth: C-section", ["c-section", "c section", "cesarean", "caesarean", "birth", "deliver"],
     [("MS-DRG", "788")]),
    ("X-ray of the arm or wrist", ["broken arm", "broken wrist", "arm x", "wrist", "forearm", "fracture"],
     [("CPT/HCPCS", "73090"), ("CPT/HCPCS", "73110")]),
    ("X-ray of the ankle or foot", ["broken ankle", "broken foot", "ankle", "foot", "sprain", "fracture"],
     [("CPT/HCPCS", "73610"), ("CPT/HCPCS", "73630")]),
    ("Chest X-ray", ["chest x", "lung x", "cough", "pneumonia"], [("CPT/HCPCS", "71046")]),
    ("CT scan of the head", ["head scan", "brain scan", "ct head", "ct brain", "concussion", "head injury"],
     [("CPT/HCPCS", "70450")]),
    ("MRI of the brain", ["brain mri", "mri brain", "mri head", "head mri", "brain scan"], [("CPT/HCPCS", "70551")]),
    ("MRI of the lower back", ["back mri", "mri back", "spine", "back pain", "lumbar", "sciatica"],
     [("CPT/HCPCS", "72148")]),
    ("MRI of the knee", ["knee mri", "mri knee", "knee pain", "torn meniscus", "acl"], [("CPT/HCPCS", "73721")]),
    ("CT scan of the chest", ["ct chest", "chest ct", "lung scan"], [("CPT/HCPCS", "71250")]),
    ("CT scan of the abdomen", ["ct abdomen", "belly scan", "stomach scan", "abdominal ct", "stomach pain"],
     [("CPT/HCPCS", "74177")]),
    ("Ultrasound of the abdomen", ["belly ultrasound", "abdominal ultrasound", "stomach ultrasound", "ultrasound",
                                   "gallstone"], [("CPT/HCPCS", "76700")]),
    ("Heart tracing (EKG)", ["ekg", "ecg", "heart test", "heart tracing", "palpitation", "chest pain"],
     [("CPT/HCPCS", "93005"), ("CPT/HCPCS", "93000")]),
    ("Heart ultrasound (echocardiogram)", ["echo", "heart ultrasound", "heart test", "heart scan"],
     [("CPT/HCPCS", "93306")]),
    ("Heart stress test", ["stress test", "treadmill test", "heart test"], [("CPT/HCPCS", "93015")]),
    ("Blood sugar and diabetes tests", ["diabetes", "blood sugar", "a1c", "glucose"],
     [("CPT/HCPCS", "83036"), ("CPT/HCPCS", "82947")]),
    ("Cholesterol test", ["cholesterol", "lipid"], [("CPT/HCPCS", "80061")]),
    ("Thyroid test", ["thyroid", "tsh"], [("CPT/HCPCS", "84443")]),
    ("General blood work", ["blood work", "bloodwork", "blood test", "blood panel", "lab work", "labs"],
     [("CPT/HCPCS", "80053"), ("CPT/HCPCS", "85025"), ("CPT/HCPCS", "80048"), ("CPT/HCPCS", "36415")]),
    ("Vitamin D test", ["vitamin d"], [("CPT/HCPCS", "82306")]),
    ("Urine test", ["urine", "pee test", "uti", "urinalysis"], [("CPT/HCPCS", "81001")]),
    ("Pregnancy test", ["pregnancy test", "am i pregnant"], [("CPT/HCPCS", "81025")]),
    ("COVID-19 test", ["covid", "coronavirus"], [("CPT/HCPCS", "87635")]),
    ("Flu test", ["flu", "influenza"], [("CPT/HCPCS", "87804")]),
    ("Strep throat test", ["strep", "sore throat"], [("CPT/HCPCS", "87880")]),
    ("Prostate (PSA) test", ["prostate", "psa"], [("CPT/HCPCS", "84153")]),
    ("Pap smear", ["pap", "cervical"], [("CPT/HCPCS", "88175")]),
    ("Screening mammogram", ["mammogram", "breast screening", "breast x"], [("CPT/HCPCS", "77067")]),
    ("Bone density scan", ["bone density", "osteoporosis", "dexa"], [("CPT/HCPCS", "77080")]),
    ("Colonoscopy", ["colonoscopy", "colon cancer", "colon screening"],
     [("CPT/HCPCS", "45378"), ("CPT/HCPCS", "45380")]),
    ("Upper endoscopy", ["endoscopy", "stomach camera", "egd", "acid reflux"], [("CPT/HCPCS", "43239")]),
    ("Emergency room visit", ["emergency", "er visit", "e.r.", "urgent"],
     [("CPT/HCPCS", "99283"), ("CPT/HCPCS", "99284"), ("CPT/HCPCS", "99285")]),
    ("Doctor's office visit", ["doctor visit", "office visit", "checkup", "check-up", "check up", "appointment"],
     [("CPT/HCPCS", "99213"), ("CPT/HCPCS", "99203")]),
    ("Stitches", ["stitches", "cut", "laceration", "wound"], [("CPT/HCPCS", "12001")]),
    ("Physical therapy session", ["physical therapy", "physio", "rehab"], [("CPT/HCPCS", "97110")]),
    ("Therapy session (45 minutes)", ["therapy", "counseling", "counselling", "psychotherapy", "mental health"],
     [("CPT/HCPCS", "90834")]),
    ("Sleep study", ["sleep study", "sleep apnea", "snoring"], [("CPT/HCPCS", "95810")]),
    ("Breathing test", ["breathing test", "asthma", "lung function", "spirometry"], [("CPT/HCPCS", "94010")]),
    ("Appendix removal", ["appendix", "appendicitis", "appendectomy"], [("CPT/HCPCS", "44970")]),
    ("Gallbladder removal", ["gallbladder", "gall bladder", "gallstone"], [("CPT/HCPCS", "47562")]),
    ("Tonsil removal", ["tonsil", "adenoid"], [("CPT/HCPCS", "42820"), ("CPT/HCPCS", "42826")]),
    ("Cataract surgery", ["cataract"], [("CPT/HCPCS", "66984")]),
    ("Hernia repair", ["hernia"], [("CPT/HCPCS", "49505")]),
    ("Knee replacement", ["knee replacement", "new knee"], [("CPT/HCPCS", "27447"), ("MS-DRG", "470")]),
    ("Hip replacement", ["hip replacement", "new hip"], [("CPT/HCPCS", "27130"), ("MS-DRG", "470")]),
    ("Knee arthroscopy", ["knee surgery", "arthroscopy", "meniscus"], [("CPT/HCPCS", "29881")]),
    ("Joint injection", ["joint injection", "cortisone", "steroid shot"], [("CPT/HCPCS", "20610")]),
    ("Epidural injection for back pain", ["epidural", "back injection"], [("CPT/HCPCS", "62323")]),
]

# Visits that involve several services, added together into one total per hospital.
# Each entry: (key, icon, name, what it is, [(code type, code, plain name of the part), ...]).
PACKAGES = [
    ("blood-work", "🧪", "Routine blood work", "A blood draw with the four most common lab panels",
     [("CPT/HCPCS", "36415", "Blood draw"), ("CPT/HCPCS", "80053", "Metabolic panel"),
      ("CPT/HCPCS", "85025", "Complete blood count"), ("CPT/HCPCS", "80061", "Cholesterol panel"),
      ("CPT/HCPCS", "84443", "Thyroid test")]),
    ("er-arm", "🩹", "Emergency visit for a possible broken arm", "An emergency room visit with an arm X-ray",
     [("CPT/HCPCS", "99283", "Emergency room visit"), ("CPT/HCPCS", "73090", "X-ray of the forearm")]),
    ("er-chest", "🫁", "Emergency visit for chest pain",
     "An emergency room visit with a chest X-ray and a heart tracing",
     [("CPT/HCPCS", "99284", "Emergency room visit"), ("CPT/HCPCS", "71046", "Chest X-ray"),
      ("CPT/HCPCS", "93005", "Heart tracing (EKG)")]),
    ("colonoscopy", "🔬", "Colonoscopy with biopsy", "A colonoscopy where a sample is taken and examined in the lab",
     [("CPT/HCPCS", "45380", "Colonoscopy with biopsy"), ("CPT/HCPCS", "88305", "Lab examination of the sample")]),
    ("diabetes", "🩸", "Diabetes check-up", "An office visit with a blood draw, an A1c test and a metabolic panel",
     [("CPT/HCPCS", "99213", "Office visit"), ("CPT/HCPCS", "36415", "Blood draw"),
      ("CPT/HCPCS", "83036", "A1c test"), ("CPT/HCPCS", "80053", "Metabolic panel")]),
    ("prenatal", "🤰", "Prenatal visit with ultrasound", "An office visit with a pregnancy ultrasound",
     [("CPT/HCPCS", "99213", "Office visit"), ("CPT/HCPCS", "76805", "Pregnancy ultrasound")]),
]

FAQ = [
    ("Are these the prices I will actually pay?",
     "Not exactly. These are the prices each hospital publishes. If you pay yourself, the cash price is usually "
     "close to what you are charged for that one service. With insurance, your share depends on your deductible, "
     "coinsurance and copay. Always call the hospital's billing office to confirm before you go."),
    ("What does the price include?",
     "Each price is for one billing code, which is usually the hospital's charge for that service. A visit often "
     "involves several codes, and a doctor's fee, anaesthesia or lab work may be billed separately."),
    ("Why does a hospital show a range instead of one price?",
     "The hospital lists the same billing code on several lines, for example one line for the full service and "
     "another for only part of it. When the lines are very far apart, the app compares hospitals on the higher "
     "price, so that nobody is drawn to a figure that covers only part of the service."),
    ("What is a package of services?",
     "A visit usually involves more than one billing code. A package adds up the usual codes for a common visit, "
     "such as an emergency room visit plus an X-ray, so you see one total per hospital. Only hospitals that publish "
     "a price for every part are listed. Your own visit may include different services."),
    ("Where do the prices come from?",
     "From the machine-readable price file that every United States hospital must publish under the federal "
     "Hospital Price Transparency rule. The app downloads each file from the hospital's own website and shows "
     "the numbers as published. A price the hospital left blank is shown as not published, never estimated."),
    ("How current are the prices?",
     "Each hospital updates its own file, usually once a year. The date of every hospital's file is shown beside "
     "its prices, and prices more than a year old are marked as old."),
    ("Where do the ratings come from?",
     "From Medicare's national patient survey, in which a random sample of recent patients review their hospital "
     "stay. The stars and the share of patients who would recommend the hospital come from that survey. Hospitals "
     "that operate under one licence share a rating, and a few specialty hospitals are not rated."),
    ("Why isn't my insurance plan listed?",
     "The insurance list shows the companies that appear in at least three hospitals' files. Open a hospital to "
     "see every plan it lists by its exact name. If your plan is not there, the hospital may be out of network "
     "for it."),
    ("How does the cost calculator work?",
     "You type in three numbers from your insurance plan: the deductible you still have to meet, your coinsurance "
     "percentage and your copay. The calculator applies them to the plan's price for that service. It does not "
     "know your out-of-pocket maximum or whether the hospital is in your network, so treat the result as a rough "
     "guide."),
    ("Why are some hospitals missing for a service?",
     "A hospital is listed only if its file contains a price for that billing code. It may not offer the service, "
     "or it may file it under a different code."),
    ("Do you collect any personal information?",
     "No. There is no sign-up, and the ZIP code and plan details you type are used only to calculate what you see "
     "on the page."),
]

FAQ_ES = [
    ("¿Estos son los precios que realmente voy a pagar?",
     "No exactamente. Son los precios que publica cada hospital. Si paga por su cuenta, el precio en efectivo suele "
     "ser cercano a lo que le cobran por ese servicio. Con seguro, su parte depende de su deducible, coseguro y "
     "copago. Llame siempre a la oficina de facturación del hospital para confirmar antes de ir."),
    ("¿Qué incluye el precio?",
     "Cada precio corresponde a un código de facturación, que normalmente es el cargo del hospital por ese servicio. "
     "Una visita suele incluir varios códigos, y los honorarios del médico, la anestesia o el laboratorio pueden "
     "facturarse aparte."),
    ("¿Por qué un hospital muestra un rango en lugar de un solo precio?",
     "El hospital registra el mismo código en varias líneas, por ejemplo una para el servicio completo y otra para "
     "solo una parte. Cuando las líneas son muy distintas, la aplicación compara por el precio más alto, para que "
     "nadie se guíe por una cifra que cubre solo parte del servicio."),
    ("¿Qué es un paquete de servicios?",
     "Una visita suele incluir más de un código de facturación. Un paquete suma los códigos habituales de una visita "
     "común, como una visita a emergencias más una radiografía, para mostrar un total por hospital. Solo aparecen los "
     "hospitales que publican precio para todas las partes. Su visita puede incluir otros servicios."),
    ("¿De dónde vienen los precios?",
     "Del archivo de precios que todo hospital de Estados Unidos debe publicar según la norma federal de "
     "transparencia de precios. La aplicación descarga cada archivo del sitio del propio hospital y muestra los "
     "números tal como se publican. Un precio que el hospital dejó en blanco aparece como no publicado, nunca estimado."),
    ("¿Qué tan actuales son los precios?",
     "Cada hospital actualiza su archivo, normalmente una vez al año. La fecha del archivo de cada hospital aparece "
     "junto a sus precios, y los precios de más de un año se marcan como antiguos."),
    ("¿De dónde vienen las calificaciones?",
     "De la encuesta nacional de pacientes de Medicare, en la que una muestra aleatoria de pacientes recientes evalúa "
     "su estancia en el hospital. Los hospitales que operan con una misma licencia comparten calificación, y algunos "
     "hospitales especializados no tienen calificación."),
    ("¿Por qué no aparece mi plan de seguro?",
     "La lista muestra las aseguradoras que aparecen en los archivos de al menos tres hospitales. Abra un hospital "
     "para ver cada plan con su nombre exacto. Si su plan no está, es posible que el hospital esté fuera de su red."),
    ("¿Cómo funciona la calculadora de costos?",
     "Usted ingresa tres números de su plan: el deducible que le falta por cubrir, su porcentaje de coseguro y su "
     "copago. La calculadora los aplica al precio del plan para ese servicio. No conoce su gasto máximo anual ni si "
     "el hospital está en su red, así que tome el resultado como una guía aproximada."),
    ("¿Por qué faltan algunos hospitales para un servicio?",
     "Un hospital aparece solo si su archivo contiene un precio para ese código de facturación. Puede que no ofrezca "
     "el servicio o que lo registre con otro código."),
    ("¿Recopilan información personal?",
     "No. No hay registro, y el código postal y los datos del plan que usted escribe se usan solo para calcular lo "
     "que ve en la página."),
]

# Spanish search words -> the English words the search understands. Longer phrases come first.
SPANISH_SEARCH = [
    ("brazo roto", "broken arm"), ("muñeca rota", "broken wrist"), ("tobillo roto", "broken ankle"),
    ("pie roto", "broken foot"), ("ecografía de embarazo", "pregnancy ultrasound"),
    ("ultrasonido de embarazo", "pregnancy ultrasound"), ("prueba de embarazo", "pregnancy test"),
    ("análisis de sangre", "blood test"), ("examen de sangre", "blood test"), ("prueba de sangre", "blood test"),
    ("azúcar en la sangre", "blood sugar"), ("sala de emergencias", "emergency"), ("dolor de pecho", "chest pain"),
    ("dolor de espalda", "back pain"), ("dolor de garganta", "sore throat"), ("dolor de rodilla", "knee pain"),
    ("reemplazo de rodilla", "knee replacement"), ("reemplazo de cadera", "hip replacement"),
    ("terapia física", "physical therapy"), ("fisioterapia", "physical therapy"),
    ("densidad ósea", "bone density"), ("estudio del sueño", "sleep study"), ("vitamina d", "vitamin d"),
    ("resonancia magnética", "mri"), ("resonancia", "mri"), ("tomografía", "ct"), ("radiografía", "x-ray"),
    ("rayos x", "x-ray"), ("ecografía", "ultrasound"), ("ultrasonido", "ultrasound"),
    ("electrocardiograma", "ekg"), ("ecocardiograma", "echo"), ("mamografía", "mammogram"),
    ("colonoscopia", "colonoscopy"), ("endoscopia", "endoscopy"), ("embarazo", "pregnan"), ("parto", "birth"),
    ("cesárea", "cesarean"), ("emergencia", "emergency"), ("urgencias", "emergency"), ("colesterol", "cholesterol"),
    ("tiroides", "thyroid"), ("orina", "urine"), ("gripe", "flu"), ("próstata", "prostate"),
    ("papanicolau", "pap"), ("puntos", "stitches"), ("sutura", "stitches"), ("apéndice", "appendix"),
    ("vesícula", "gallbladder"), ("amígdalas", "tonsil"), ("cataratas", "cataract"), ("hernia", "hernia"),
    ("diabetes", "diabetes"), ("consulta", "office visit"), ("cita médica", "office visit"),
    ("cerebro", "brain"), ("cabeza", "head"), ("rodilla", "knee"), ("espalda", "back"), ("pecho", "chest"),
    ("tórax", "chest"), ("abdomen", "abdomen"), ("estómago", "stomach"), ("corazón", "heart"),
    ("sangre", "blood"), ("terapia", "therapy"),
]
