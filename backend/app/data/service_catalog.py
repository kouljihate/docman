"""Reference catalogue of the six service lines and their main tasks.

Every value is written in the three interface languages so the seeded data can
follow the language selected in the UI: ``fr`` is the reference text stored in
the base ``name`` / ``title`` / ``description`` fields, and ``name_i18n``,
``title_i18n`` and ``description_i18n`` carry all three.

``title`` is the short label shown in tables, ``text`` the full instruction kept
as the description.
"""

LANGUAGES = ("en", "fr", "ar")

SERVICES = [
    {
        "name": {
            "fr": "Conseil juridique",
            "en": "Legal advisory",
            "ar": "الاستشارة القانونية",
        },
        "tasks": [
            {
                "title": {
                    "fr": "Conseiller le client sur le droit des sociétés",
                    "en": "Advise on company law",
                    "ar": "المشورة في قانون الشركات",
                },
                "text": {
                    "fr": "Conseiller le client sur le droit des sociétés, les contrats et les obligations légales.",
                    "en": "Advise the client on company law, contracts and legal obligations.",
                    "ar": "تقديم المشورة للعميل في قانون الشركات والعقود والالتزامات القانونية.",
                },
            },
            {
                "title": {
                    "fr": "Rédiger et réviser les statuts",
                    "en": "Draft and review statutes",
                    "ar": "صياغة النظام الأساسي",
                },
                "text": {
                    "fr": "Rédiger et réviser les statuts, pactes d'associés, contrats commerciaux, baux, procès-verbaux et résolutions.",
                    "en": "Draft and review the articles of association, shareholder agreements, commercial contracts, leases, minutes and resolutions.",
                    "ar": "صياغة ومراجعة النظام الأساسي واتفاقيات الشركاء والعقود التجارية وعقود الإيجار والمحاضر والقرارات.",
                },
            },
            {
                "title": {
                    "fr": "Assister dans la création",
                    "en": "Assist with company formation",
                    "ar": "المساعدة في تأسيس الشركة",
                },
                "text": {
                    "fr": "Assister dans la création, la modification, la transformation, la dissolution ou la liquidation d'une société.",
                    "en": "Assist with the creation, amendment, conversion, dissolution or liquidation of a company.",
                    "ar": "المساعدة في إنشاء الشركة أو تعديلها أو تحويلها أو حلها أو تصفيتها.",
                },
            },
            {
                "title": {
                    "fr": "Accompagner les opérations de cession",
                    "en": "Support transfer and merger deals",
                    "ar": "مواكبة عمليات التنازل والاندماج",
                },
                "text": {
                    "fr": "Accompagner les opérations de cession, fusion, augmentation ou réduction de capital.",
                    "en": "Support transfer, merger, capital increase or reduction transactions.",
                    "ar": "مواكبة عمليات التنازل أو الاندماج أو زيادة رأس المال أو تخفيضه.",
                },
            },
            {
                "title": {
                    "fr": "Vérifier la conformité juridique",
                    "en": "Check legal compliance",
                    "ar": "التحقق من المطابقة القانونية",
                },
                "text": {
                    "fr": "Vérifier la conformité juridique des documents et procédures.",
                    "en": "Check the legal compliance of documents and procedures.",
                    "ar": "التحقق من المطابقة القانونية للوثائق والإجراءات.",
                },
            },
            {
                "title": {
                    "fr": "Représenter ou assister le client",
                    "en": "Represent the client in procedures",
                    "ar": "تمثيل العميل في الإجراءات",
                },
                "text": {
                    "fr": "Représenter ou assister le client dans les démarches administratives et, si nécessaire, dans les contentieux.",
                    "en": "Represent or assist the client in administrative procedures and, where needed, in litigation.",
                    "ar": "تمثيل العميل أو مساعدته في الإجراءات الإدارية، وعند الحاجة في النزاعات القضائية.",
                },
            },
        ],
    },
    {
        "name": {
            "fr": "Conseil fiscal",
            "en": "Tax advisory",
            "ar": "الاستشارة الجبائية",
        },
        "tasks": [
            {
                "title": {
                    "fr": "Analyser la situation fiscale de l'entreprise",
                    "en": "Analyse the tax position",
                    "ar": "تحليل الوضع الجبائي",
                },
                "text": {
                    "fr": "Analyser la situation fiscale de l'entreprise et identifier les obligations applicables.",
                    "en": "Analyse the company's tax position and identify the applicable obligations.",
                    "ar": "تحليل الوضع الجبائي للمؤسسة وتحديد الالتزامات المطبقة.",
                },
            },
            {
                "title": {
                    "fr": "Établir ou superviser les déclarations fiscales",
                    "en": "Prepare tax returns",
                    "ar": "إعداد التصريحات الجبائية",
                },
                "text": {
                    "fr": "Établir ou superviser les déclarations fiscales : TVA, impôt sur les sociétés, impôt sur le revenu, taxes locales, etc.",
                    "en": "Prepare or supervise tax returns: VAT, corporate tax, income tax, local taxes, etc.",
                    "ar": "إعداد أو الإشراف على التصريحات الجبائية: الرسم على القيمة المضافة، ضريبة الشركات، ضريبة الدخل، الرسوم المحلية، إلخ.",
                },
            },
            {
                "title": {
                    "fr": "Conseiller sur l'optimisation fiscale légale",
                    "en": "Advise on tax optimisation",
                    "ar": "المشورة في التحسين الجبائي",
                },
                "text": {
                    "fr": "Conseiller sur l'optimisation fiscale légale et la planification fiscale.",
                    "en": "Advise on lawful tax optimisation and tax planning.",
                    "ar": "تقديم المشورة بشأن التحسين الجبائي المشروع والتخطيط الجبائي.",
                },
            },
            {
                "title": {
                    "fr": "Assister lors des contrôles fiscaux",
                    "en": "Assist during tax audits",
                    "ar": "المساعدة في المراقبة الجبائية",
                },
                "text": {
                    "fr": "Assister lors des contrôles fiscaux et préparer les réponses aux demandes de l'administration.",
                    "en": "Assist during tax audits and prepare the answers to the authorities' requests.",
                    "ar": "المساعدة أثناء المراقبة الجبائية وإعداد الردود على طلبات الإدارة.",
                },
            },
            {
                "title": {
                    "fr": "Accompagner le client dans les réclamations",
                    "en": "Support tax claims and appeals",
                    "ar": "مواكبة المطالبات الجبائية",
                },
                "text": {
                    "fr": "Accompagner le client dans les réclamations, recours et contentieux fiscaux.",
                    "en": "Support the client in tax claims, appeals and disputes.",
                    "ar": "مواكبة العميل في المطالبات والطعون والنزاعات الجبائية.",
                },
            },
            {
                "title": {
                    "fr": "Mettre à jour le client sur les évolutions",
                    "en": "Keep the client informed on tax rules",
                    "ar": "إطلاع العميل على التشريع الجبائي",
                },
                "text": {
                    "fr": "Mettre à jour le client sur les évolutions de la réglementation fiscale.",
                    "en": "Keep the client up to date on changes in tax rules.",
                    "ar": "إطلاع العميل على تطورات التشريع الجبائي.",
                },
            },
        ],
    },
    {
        "name": {
            "fr": "Organisation entreprise",
            "en": "Business organisation",
            "ar": "تنظيم المؤسسة",
        },
        "tasks": [
            {
                "title": {
                    "fr": "Réaliser un diagnostic de l'organisation",
                    "en": "Assess the organisation",
                    "ar": "تشخيص تنظيم المؤسسة",
                },
                "text": {
                    "fr": "Réaliser un diagnostic de l'organisation existante : processus, responsabilités, outils et performances.",
                    "en": "Assess the existing organisation: processes, responsibilities, tools and performance.",
                    "ar": "إجراء تشخيص للتنظيم القائم: العمليات والمسؤوليات والأدوات والأداء.",
                },
            },
            {
                "title": {
                    "fr": "Définir ou améliorer l'organigramme",
                    "en": "Define the organisation chart",
                    "ar": "تحسين الهيكل التنظيمي",
                },
                "text": {
                    "fr": "Définir ou améliorer l'organigramme, les fiches de poste et les procédures internes.",
                    "en": "Define or improve the organisation chart, job descriptions and internal procedures.",
                    "ar": "تحديد أو تحسين الهيكل التنظيمي وبطاقات الوظائف والإجراءات الداخلية.",
                },
            },
            {
                "title": {
                    "fr": "Mettre en place des outils de gestion",
                    "en": "Set up management tools",
                    "ar": "إرساء أدوات التسيير",
                },
                "text": {
                    "fr": "Mettre en place des outils de gestion : planning, tableaux de bord, suivi des dossiers, gestion documentaire.",
                    "en": "Set up management tools: planning, dashboards, case tracking and document management.",
                    "ar": "إرساء أدوات التسيير: التخطيط ولوحات القيادة ومتابعة الملفات وإدارة الوثائق.",
                },
            },
            {
                "title": {
                    "fr": "Optimiser les flux administratifs",
                    "en": "Streamline administrative flows",
                    "ar": "تحسين التدفقات الإدارية",
                },
                "text": {
                    "fr": "Optimiser les flux administratifs, commerciaux, financiers et RH.",
                    "en": "Streamline administrative, sales, financial and HR flows.",
                    "ar": "تحسين التدفقات الإدارية والتجارية والمالية والموارد البشرية.",
                },
            },
            {
                "title": {
                    "fr": "Conseiller sur la gestion du personnel",
                    "en": "Advise on staff management",
                    "ar": "المشورة في إدارة الموظفين",
                },
                "text": {
                    "fr": "Conseiller sur la gestion du personnel, le recrutement, la formation et la motivation des équipes.",
                    "en": "Advise on staff management, recruitment, training and team motivation.",
                    "ar": "تقديم المشورة في إدارة الموظفين والتوظيف والتكوين وتحفيز الفرق.",
                },
            },
            {
                "title": {
                    "fr": "Accompagner la digitalisation",
                    "en": "Support digitalisation",
                    "ar": "مواكبة الرقمنة",
                },
                "text": {
                    "fr": "Accompagner la digitalisation et l'amélioration de la qualité des services.",
                    "en": "Support digitalisation and service quality improvement.",
                    "ar": "مواكبة الرقمنة وتحسين جودة الخدمات.",
                },
            },
        ],
    },
    {
        "name": {
            "fr": "Étude",
            "en": "Studies",
            "ar": "الدراسات",
        },
        "tasks": [
            {
                "title": {
                    "fr": "Réaliser des études de faisabilité",
                    "en": "Carry out feasibility studies",
                    "ar": "دراسات الجدوى",
                },
                "text": {
                    "fr": "Réaliser des études de faisabilité pour un projet, une activité ou un investissement.",
                    "en": "Carry out feasibility studies for a project, activity or investment.",
                    "ar": "إعداد دراسات الجدوى لمشروع أو نشاط أو استثمار.",
                },
            },
            {
                "title": {
                    "fr": "Élaborer des études de marché",
                    "en": "Produce market studies",
                    "ar": "دراسات السوق",
                },
                "text": {
                    "fr": "Élaborer des études de marché : analyse de la demande, de la concurrence, des prix et des clients cibles.",
                    "en": "Produce market studies: demand, competition, pricing and target customers.",
                    "ar": "إعداد دراسات السوق: تحليل الطلب والمنافسة والأسعار والعملاء المستهدفين.",
                },
            },
            {
                "title": {
                    "fr": "Préparer des études financières",
                    "en": "Prepare financial studies",
                    "ar": "الدراسات المالية",
                },
                "text": {
                    "fr": "Préparer des études financières : prévisionnel, budget, rentabilité, seuil de rentabilité et plan de financement.",
                    "en": "Prepare financial studies: forecasts, budget, profitability, break-even point and funding plan.",
                    "ar": "إعداد الدراسات المالية: التوقعات والميزانية والمردودية وعتبة المردودية وخطة التمويل.",
                },
            },
            {
                "title": {
                    "fr": "Réaliser des études économiques",
                    "en": "Carry out economic studies",
                    "ar": "الدراسات الاقتصادية",
                },
                "text": {
                    "fr": "Réaliser des études économiques, commerciales ou stratégiques.",
                    "en": "Carry out economic, commercial or strategic studies.",
                    "ar": "إعداد دراسات اقتصادية أو تجارية أو استراتيجية.",
                },
            },
            {
                "title": {
                    "fr": "Analyser les risques",
                    "en": "Analyse risks",
                    "ar": "تحليل المخاطر",
                },
                "text": {
                    "fr": "Analyser les risques et proposer des recommandations pour la prise de décision.",
                    "en": "Analyse risks and provide recommendations for decision-making.",
                    "ar": "تحليل المخاطر وتقديم توصيات لاتخاذ القرار.",
                },
            },
            {
                "title": {
                    "fr": "Rédiger un rapport d'étude",
                    "en": "Write the study report",
                    "ar": "إعداد تقرير الدراسة",
                },
                "text": {
                    "fr": "Rédiger un rapport d'étude et présenter les résultats au client.",
                    "en": "Write the study report and present the results to the client.",
                    "ar": "إعداد تقرير الدراسة وتقديم النتائج للعميل.",
                },
            },
        ],
    },
    {
        "name": {
            "fr": "Domiciliation",
            "en": "Domiciliation",
            "ar": "التوطين",
        },
        "tasks": [
            {
                "title": {
                    "fr": "Mettre à disposition une adresse commerciale",
                    "en": "Provide a business address",
                    "ar": "توفير عنوان تجاري",
                },
                "text": {
                    "fr": "Mettre à disposition une adresse commerciale, administrative et légale pour l'entreprise.",
                    "en": "Provide a commercial, administrative and legal address for the company.",
                    "ar": "توفير عنوان تجاري وإداري وقانوني للمؤسسة.",
                },
            },
            {
                "title": {
                    "fr": "Fournir les attestations de domiciliation",
                    "en": "Issue domiciliation certificates",
                    "ar": "شهادات التوطين",
                },
                "text": {
                    "fr": "Fournir les attestations de domiciliation nécessaires aux démarches de création ou d'immatriculation.",
                    "en": "Issue the domiciliation certificates required for incorporation or registration.",
                    "ar": "تسليم شهادات التوطين اللازمة لإجراءات التأسيس أو التسجيل.",
                },
            },
            {
                "title": {
                    "fr": "Réceptionner, trier et transmettre le courrier",
                    "en": "Handle the client's mail",
                    "ar": "معالجة بريد العميل",
                },
                "text": {
                    "fr": "Réceptionner, trier et transmettre le courrier administratif et commercial du client.",
                    "en": "Receive, sort and forward the client's administrative and commercial mail.",
                    "ar": "استقبال وفرز وإرسال بريد العميل الإداري والتجاري.",
                },
            },
            {
                "title": {
                    "fr": "Assurer la gestion des appels",
                    "en": "Handle incoming calls",
                    "ar": "تسيير المكالمات الواردة",
                },
                "text": {
                    "fr": "Assurer la gestion des appels, messages ou demandes entrantes selon la formule choisie.",
                    "en": "Handle incoming calls, messages or requests according to the chosen package.",
                    "ar": "تسيير المكالمات والرسائل والطلبات الواردة حسب الصيغة المختارة.",
                },
            },
            {
                "title": {
                    "fr": "Mettre à disposition un espace de travail",
                    "en": "Provide workspace and meeting room",
                    "ar": "توفير فضاء العمل وقاعة الاجتماعات",
                },
                "text": {
                    "fr": "Mettre à disposition, selon l'offre, un espace de travail, une salle de réunion ou des services de secrétariat.",
                    "en": "Provide a workspace, a meeting room or secretarial services depending on the offer.",
                    "ar": "توفير فضاء عمل أو قاعة اجتماعات أو خدمات سكرتارية حسب العرض.",
                },
            },
            {
                "title": {
                    "fr": "Accompagner le client dans ses formalités",
                    "en": "Support head-office formalities",
                    "ar": "مواكبة إجراءات المقر الاجتماعي",
                },
                "text": {
                    "fr": "Accompagner le client dans ses formalités administratives liées à son siège social.",
                    "en": "Support the client with the administrative formalities linked to its registered office.",
                    "ar": "مواكبة العميل في إجراءاته الإدارية المتعلقة بمقره الاجتماعي.",
                },
            },
        ],
    },
    {
        "name": {
            "fr": "Recouvrement des créances",
            "en": "Debt collection",
            "ar": "تحصيل الديون",
        },
        "tasks": [
            {
                "title": {
                    "fr": "Identifier, vérifier et classer les créances",
                    "en": "Classify unpaid receivables",
                    "ar": "ترتيب الديون غير المسددة",
                },
                "text": {
                    "fr": "Identifier, vérifier et classer les créances impayées du client.",
                    "en": "Identify, verify and classify the client's unpaid receivables.",
                    "ar": "تحديد الديون غير المسددة للعميل والتحقق منها وترتيبها.",
                },
            },
            {
                "title": {
                    "fr": "Envoyer des relances amiables",
                    "en": "Send friendly reminders",
                    "ar": "إرسال التذكيرات الودية",
                },
                "text": {
                    "fr": "Envoyer des relances amiables par téléphone, e-mail ou courrier.",
                    "en": "Send friendly reminders by phone, e-mail or post.",
                    "ar": "إرسال تذكيرات ودية عبر الهاتف أو البريد الإلكتروني أو البريد العادي.",
                },
            },
            {
                "title": {
                    "fr": "Négocier des échéanciers de paiement",
                    "en": "Negotiate payment schedules",
                    "ar": "التفاوض على جداول الدفع",
                },
                "text": {
                    "fr": "Négocier des échéanciers de paiement ou des accords de règlement avec les débiteurs.",
                    "en": "Negotiate payment schedules or settlement agreements with debtors.",
                    "ar": "التفاوض على جداول الدفع أو اتفاقات التسوية مع المدينين.",
                },
            },
            {
                "title": {
                    "fr": "Mettre en demeure le débiteur",
                    "en": "Serve formal notice",
                    "ar": "توجيه إنذار رسمي",
                },
                "text": {
                    "fr": "Mettre en demeure le débiteur lorsque la relance amiable échoue.",
                    "en": "Serve formal notice on the debtor when friendly reminders fail.",
                    "ar": "توجيه إنذار رسمي إلى المدين عند فشل التذكير الودي.",
                },
            },
            {
                "title": {
                    "fr": "Préparer les dossiers d'action judiciaire",
                    "en": "Prepare legal action files",
                    "ar": "إعداد ملفات المتابعة القضائية",
                },
                "text": {
                    "fr": "Préparer les dossiers nécessaires à une action judiciaire, en coordination avec un avocat si nécessaire.",
                    "en": "Prepare the files needed for legal action, in coordination with a lawyer if required.",
                    "ar": "إعداد الملفات اللازمة للمتابعة القضائية بالتنسيق مع محام عند الحاجة.",
                },
            },
            {
                "title": {
                    "fr": "Suivre les paiements et informer le client",
                    "en": "Track payments",
                    "ar": "متابعة المدفوعات",
                },
                "text": {
                    "fr": "Suivre les paiements, mettre à jour l'état des créances et informer régulièrement le client.",
                    "en": "Track payments, update the receivables status and keep the client informed.",
                    "ar": "متابعة المدفوعات وتحديث وضعية الديون وإعلام العميل بانتظام.",
                },
            },
        ],
    },
]


def normalize(text):
    """Case-fold and collapse whitespace for catalogue matching."""
    return " ".join((text or "").split()).strip().rstrip(" .!?").casefold()


def service_for_name(name):
    """Return the catalogue service matching a name in any language."""
    wanted = normalize(name)
    if not wanted:
        return None
    for service in SERVICES:
        if any(normalize(value) == wanted for value in service["name"].values()):
            return service
    return None


def task_for(text):
    """Return the catalogue task matching a full text or a short title."""
    wanted = normalize(text)
    if not wanted:
        return None
    for service in SERVICES:
        for task in service["tasks"]:
            values = list(task["text"].values()) + list(task["title"].values())
            if any(normalize(value) == wanted for value in values):
                return task
    return None
