"""
ERP Setup – Multilingual Default Data

All default data for the setup wizard and erp_first_setup management command.
Each translatable string is stored as a dict: {'ar': ..., 'en': ..., 'id': ...}

Usage:
    from erp.setup_defaults import get_text, CHART_OF_ACCOUNTS, ...
    name = get_text(item['name'], lang='en')  # → "Cash"
"""

from decimal import Decimal


# =============================================================================
# Helpers
# =============================================================================


def _t(ar: str, en: str, id: str = "") -> dict:
    """Create a trilingual text dict.  *id* defaults to English if omitted."""
    return {"ar": ar, "en": en, "id": id or en}


def get_text(translations: dict | str, lang: str = "en") -> str:
    """Return the text for *lang*, falling back to English then Arabic."""
    if isinstance(translations, str):
        return translations
    return translations.get(lang) or translations.get("en") or translations.get("ar", "")  # type: ignore


# =============================================================================
# Setup Steps
# =============================================================================

SETUP_STEPS = [
    {"number": 1, "name": _t("العملة", "Currency", "Mata Uang"), "icon": "bi-currency-exchange"},
    {"number": 2, "name": _t("الشركة", "Company", "Perusahaan"), "icon": "bi-building"},
    {"number": 3, "name": _t("السنة المالية", "Fiscal Year", "Tahun Fiskal"), "icon": "bi-calendar3"},
    {"number": 4, "name": _t("الضرائب", "Taxes", "Pajak"), "icon": "bi-percent"},
    {"number": 5, "name": _t("طرق الدفع", "Payment Methods", "Metode Pembayaran"), "icon": "bi-credit-card"},
    {"number": 6, "name": _t("الحسابات", "Chart of Accounts", "Bagan Akun"), "icon": "bi-journal-text"},
    {"number": 7, "name": _t("المراجعة", "Review", "Tinjauan"), "icon": "bi-check-circle"},
]


def get_setup_steps(lang: str = "ar") -> list:
    """Return steps with names resolved for *lang*."""
    return [{**step, "name": get_text(step["name"], lang)} for step in SETUP_STEPS]


# =============================================================================
# Currency Map
# =============================================================================

CURRENCY_MAP = {
    "SAR": {"name": _t("ريال سعودي", "Saudi Riyal", "Riyal Saudi"), "symbol": "ر.س"},
    "AED": {"name": _t("درهم إماراتي", "UAE Dirham", "Dirham UEA"), "symbol": "د.إ"},
    "USD": {"name": _t("دولار أمريكي", "US Dollar", "Dolar AS"), "symbol": "$"},
    "EUR": {"name": _t("يورو", "Euro", "Euro"), "symbol": "€"},
    "GBP": {"name": _t("جنيه إسترليني", "British Pound", "Pound Inggris"), "symbol": "£"},
    "EGP": {"name": _t("جنيه مصري", "Egyptian Pound", "Pound Mesir"), "symbol": "ج.م"},
    "KWD": {"name": _t("دينار كويتي", "Kuwaiti Dinar", "Dinar Kuwait"), "symbol": "د.ك"},
    "QAR": {"name": _t("ريال قطري", "Qatari Riyal", "Riyal Qatar"), "symbol": "ر.ق"},
    "BHD": {"name": _t("دينار بحريني", "Bahraini Dinar", "Dinar Bahrain"), "symbol": "د.ب"},
    "OMR": {"name": _t("ريال عماني", "Omani Rial", "Rial Oman"), "symbol": "ر.ع"},
    "JOD": {"name": _t("دينار أردني", "Jordanian Dinar", "Dinar Yordania"), "symbol": "د.أ"},
    "IDR": {"name": _t("روبية إندونيسية", "Indonesian Rupiah", "Rupiah Indonesia"), "symbol": "Rp"},
}


def get_currency_choices(lang: str = "ar") -> list:
    """Return (code, display_label) tuples for a ChoiceField."""
    choices = []
    for code, info in CURRENCY_MAP.items():
        label = f"{get_text(info['name'], lang)} ({code})"
        choices.append((code, label))
    other_label = get_text(_t("عملة أخرى", "Other currency", "Mata uang lain"), lang)
    choices.append(("OTHER", other_label))
    return choices


# =============================================================================
# Chart of Accounts  (professional – aligned with erp_first_setup)
# =============================================================================


def _acct(code, name_dict, acct_type, parent=None):
    return {"code": code, "name": name_dict, "type": acct_type, "parent": parent}


# Using short type aliases resolved by callers via Account.AccountType
_A = "ASSET"
_L = "LIABILITY"
_E = "EQUITY"
_I = "INCOME"
_X = "EXPENSE"


BASE_CHART_OF_ACCOUNTS = [
    # ── Assets (1xxx) ──
    _acct("1000", _t("الأصول", "Assets", "Aset"), _A),
    _acct("1010", _t("الصندوق", "Cash", "Kas"), _A, "1000"),
    _acct("1020", _t("البنك", "Bank", "Bank"), _A, "1000"),
    _acct("1100", _t("الذمم المدينة", "Accounts Receivable", "Piutang Usaha"), _A, "1000"),
    _acct("1200", _t("المخزون", "Inventory", "Persediaan"), _A, "1000"),
    _acct("1300", _t("مصاريف مدفوعة مقدماً", "Prepaid Expenses", "Beban Dibayar Dimuka"), _A, "1000"),
    _acct(
        "1400",
        _t("بضاعة مستلمة غير مفوترة", "Goods Received Not Invoiced", "Barang Diterima Belum Difaktur"),
        _A,
        "1000",
    ),
    # Fixed assets
    _acct("1600", _t("الأصول الثابتة", "Fixed Assets", "Aset Tetap"), _A, "1000"),
    _acct("1610", _t("أراضي ومباني", "Land & Buildings", "Tanah & Bangunan"), _A, "1600"),
    _acct("1620", _t("أثاث ومعدات", "Furniture & Equipment", "Perabot & Peralatan"), _A, "1600"),
    _acct("1630", _t("مركبات", "Vehicles", "Kendaraan"), _A, "1600"),
    _acct("1640", _t("معدات تقنية وبرمجيات", "IT Equipment & Software", "Peralatan IT & Perangkat Lunak"), _A, "1600"),
    _acct("1650", _t("تحسينات مباني مستأجرة", "Leasehold Improvements", "Perbaikan Sewa"), _A, "1600"),
    # Accumulated depreciation (contra-asset)
    _acct("1700", _t("مجمع الإهلاك", "Accumulated Depreciation", "Akumulasi Penyusutan"), _A, "1000"),
    _acct("1710", _t("مجمع إهلاك – مباني", "Accum. Depr. – Buildings", "Akum. Penyusutan – Bangunan"), _A, "1700"),
    _acct(
        "1720",
        _t("مجمع إهلاك – أثاث ومعدات", "Accum. Depr. – Furniture & Equipment", "Akum. Penyusutan – Perabot"),
        _A,
        "1700",
    ),
    _acct("1730", _t("مجمع إهلاك – مركبات", "Accum. Depr. – Vehicles", "Akum. Penyusutan – Kendaraan"), _A, "1700"),
    _acct("1740", _t("مجمع إهلاك – معدات تقنية", "Accum. Depr. – IT Equipment", "Akum. Penyusutan – IT"), _A, "1700"),
    _acct(
        "1750", _t("مجمع إهلاك – تحسينات مستأجرة", "Accum. Depr. – Leasehold", "Akum. Penyusutan – Sewa"), _A, "1700"
    ),
    # ── Liabilities (2xxx) ──
    _acct("2000", _t("الالتزامات", "Liabilities", "Liabilitas"), _L),
    _acct("2100", _t("الذمم الدائنة", "Accounts Payable", "Utang Usaha"), _L, "2000"),
    _acct("2200", _t("ضريبة القيمة المضافة المستحقة", "VAT / Tax Payable", "PPN / Pajak Terutang"), _L, "2000"),
    _acct("2300", _t("رواتب مستحقة", "Salary Payable", "Utang Gaji"), _L, "2000"),
    _acct("2310", _t("تأمينات اجتماعية مستحقة", "Social Insurance Payable", "BPJS Terutang"), _L, "2300"),
    _acct("2320", _t("ضريبة دخل مستحقة", "Income Tax Payable", "Pajak Penghasilan Terutang"), _L, "2300"),
    _acct("2400", _t("مصاريف مستحقة", "Accrued Expenses", "Beban yang Masih Harus Dibayar"), _L, "2000"),
    # ── Equity (3xxx) ──
    _acct("3000", _t("حقوق الملكية", "Equity", "Ekuitas"), _E),
    _acct("3100", _t("رأس المال / الأرباح المحتجزة", "Retained Earnings", "Laba Ditahan"), _E, "3000"),
    _acct("3200", _t("فائض إعادة التقييم", "Revaluation Surplus", "Surplus Revaluasi"), _E, "3000"),
    # ── Income (4xxx) ──
    _acct("4000", _t("الإيرادات", "Revenue", "Pendapatan"), _I),
    _acct("4100", _t("إيرادات المبيعات", "Sales Revenue", "Pendapatan Penjualan"), _I, "4000"),
    _acct("4200", _t("إيرادات الخدمات", "Service Revenue", "Pendapatan Jasa"), _I, "4000"),
    _acct("4300", _t("أرباح التخلص من الأصول", "Gain on Asset Disposal", "Keuntungan Pelepasan Aset"), _I, "4000"),
    _acct("4400", _t("إيرادات أخرى", "Other Income", "Pendapatan Lainnya"), _I, "4000"),
    # ── Cost of Sales (5xxx) ──
    _acct("5000", _t("تكلفة المبيعات", "Cost of Sales", "Harga Pokok Penjualan"), _X),
    _acct("5100", _t("تكلفة البضاعة المباعة", "Cost of Goods Sold", "Harga Pokok Penjualan"), _X, "5000"),
    # ── Operating Expenses (6xxx) ──
    _acct("6000", _t("المصاريف التشغيلية", "Operating Expenses", "Beban Operasional"), _X),
    _acct("6100", _t("مصاريف الرواتب والأجور", "Salary & Wages Expense", "Beban Gaji & Upah"), _X, "6000"),
    _acct("6200", _t("تسويات المخزون", "Inventory Adjustments", "Penyesuaian Persediaan"), _X, "6000"),
    _acct("6300", _t("شطب المخزون", "Inventory Write-Off", "Penghapusan Persediaan"), _X, "6000"),
    _acct("6400", _t("مصاريف الإهلاك", "Depreciation Expense", "Beban Penyusutan"), _X, "6000"),
    _acct("6500", _t("مصاريف السفر", "Travel Expenses", "Beban Perjalanan"), _X, "6000"),
    _acct("6600", _t("إيجارات ومرافق", "Rent & Utilities", "Sewa & Utilitas"), _X, "6000"),
    _acct("6700", _t("لوازم مكتبية وعامة", "Office Supplies & General", "Perlengkapan Kantor & Umum"), _X, "6000"),
    _acct("6800", _t("خسائر التخلص من الأصول", "Loss on Asset Disposal", "Kerugian Pelepasan Aset"), _X, "6000"),
]

# Travel agency specific accounts
TRAVEL_AGENCY_ACCOUNTS = [
    _acct("4110", _t("إيرادات التذاكر", "Ticket Revenue", "Pendapatan Tiket"), _I, "4100"),
    _acct("4120", _t("إيرادات الفنادق", "Hotel Revenue", "Pendapatan Hotel"), _I, "4100"),
    _acct("4130", _t("إيرادات الرحلات السياحية", "Tour Revenue", "Pendapatan Tur"), _I, "4100"),
    _acct("4140", _t("إيرادات التأشيرات", "Visa Revenue", "Pendapatan Visa"), _I, "4100"),
    _acct("4150", _t("عمولات شركات الطيران", "Airline Commissions", "Komisi Maskapai"), _I, "4100"),
    _acct("5100", _t("تكلفة التذاكر", "Ticket Cost", "Biaya Tiket"), _X, "5000"),
    _acct("5200", _t("تكلفة الفنادق", "Hotel Cost", "Biaya Hotel"), _X, "5000"),
    _acct("5300", _t("تكلفة النقل", "Transport Cost", "Biaya Transportasi"), _X, "5000"),
]

# Services company accounts
SERVICES_ACCOUNTS = [
    _acct("4210", _t("إيرادات الاستشارات", "Consulting Revenue", "Pendapatan Konsultan"), _I, "4200"),
    _acct("4220", _t("إيرادات الصيانة", "Maintenance Revenue", "Pendapatan Pemeliharaan"), _I, "4200"),
]


def get_chart_of_accounts(preset: str = "standard") -> list:
    """Return the account list for *preset*."""
    chart = list(BASE_CHART_OF_ACCOUNTS)
    if preset == "travel_agency":
        chart.extend(TRAVEL_AGENCY_ACCOUNTS)
    elif preset == "services":
        chart.extend(SERVICES_ACCOUNTS)
    # 'standard' and 'minimal' just use the base chart
    return chart


# =============================================================================
# Tax Presets
# =============================================================================

TAX_PRESETS = {
    "sa_vat": {
        "name": _t("ضريبة القيمة المضافة", "Value Added Tax", "Pajak Pertambahan Nilai"),
        "rate": Decimal("15.00"),
    },
    "ae_vat": {
        "name": _t("ضريبة القيمة المضافة", "Value Added Tax", "Pajak Pertambahan Nilai"),
        "rate": Decimal("5.00"),
    },
    "eg_vat": {
        "name": _t("ضريبة القيمة المضافة", "Value Added Tax", "Pajak Pertambahan Nilai"),
        "rate": Decimal("14.00"),
    },
    "id_ppn": {
        "name": _t("ضريبة القيمة المضافة", "Value Added Tax", "Pajak Pertambahan Nilai"),
        "rate": Decimal("11.00"),
    },
}

ZERO_TAX_NAME = _t("بدون ضريبة", "Zero Tax", "Tanpa Pajak")


def get_tax_preset_choices(lang: str = "ar") -> list:
    """Return (key, label) tuples for the tax preset field."""
    return [
        (
            "sa_vat",
            get_text(_t("ضريبة القيمة المضافة السعودية (15%)", "Saudi VAT (15%)", "PPN Arab Saudi (15%)"), lang),
        ),
        ("ae_vat", get_text(_t("ضريبة القيمة المضافة الإماراتية (5%)", "UAE VAT (5%)", "PPN UEA (5%)"), lang)),
        ("eg_vat", get_text(_t("ضريبة القيمة المضافة المصرية (14%)", "Egypt VAT (14%)", "PPN Mesir (14%)"), lang)),
        (
            "id_ppn",
            get_text(_t("ضريبة القيمة المضافة الإندونيسية (11%)", "Indonesia VAT (11%)", "PPN Indonesia (11%)"), lang),
        ),
        ("custom", get_text(_t("ضريبة مخصصة", "Custom tax", "Pajak kustom"), lang)),
        ("none", get_text(_t("بدون ضريبة", "No tax", "Tanpa pajak"), lang)),
    ]


# =============================================================================
# Payment Methods
# =============================================================================

PAYMENT_METHODS = [
    {"code": "CASH", "name": _t("نقداً", "Cash", "Tunai"), "account_code": "1010", "requires_ref": False},
    {
        "code": "BANK",
        "name": _t("تحويل بنكي", "Bank Transfer", "Transfer Bank"),
        "account_code": "1020",
        "requires_ref": True,
    },
    {
        "code": "CC",
        "name": _t("بطاقة ائتمان", "Credit Card", "Kartu Kredit"),
        "account_code": "1020",
        "requires_ref": True,
    },
    {"code": "MADA", "name": _t("مدى", "Mada", "Mada"), "account_code": "1020", "requires_ref": True},
    {"code": "STCPAY", "name": _t("STC Pay", "STC Pay", "STC Pay"), "account_code": "1020", "requires_ref": True},
    {
        "code": "APPLEPAY",
        "name": _t("Apple Pay", "Apple Pay", "Apple Pay"),
        "account_code": "1020",
        "requires_ref": True,
    },
]


# =============================================================================
# Expense Categories
# =============================================================================

EXPENSE_CATEGORIES = [
    {
        "code": "GEN",
        "name": _t("مصاريف عامة", "General Expenses", "Beban Umum"),
        "account_code": "6000",
        "parent": None,
    },
    {
        "code": "TRV",
        "name": _t("مصاريف السفر", "Travel Expenses", "Beban Perjalanan"),
        "account_code": "6500",
        "parent": "GEN",
    },
    {
        "code": "MKT",
        "name": _t("مصاريف التسويق", "Marketing Expenses", "Beban Pemasaran"),
        "account_code": "6700",
        "parent": "GEN",
    },
    {
        "code": "SAL",
        "name": _t("مصاريف الرواتب", "Salary Expenses", "Beban Gaji"),
        "account_code": "6100",
        "parent": "GEN",
    },
    {
        "code": "OFF",
        "name": _t("مصاريف المكتب", "Office Expenses", "Beban Kantor"),
        "account_code": "6700",
        "parent": "GEN",
    },
    {
        "code": "RNT",
        "name": _t("إيجارات ومرافق", "Rent & Utilities", "Sewa & Utilitas"),
        "account_code": "6600",
        "parent": "GEN",
    },
]


# =============================================================================
# Asset Categories (from erp_first_setup – professional defaults)
# =============================================================================

ASSET_CATEGORIES = [
    {
        "name": _t("أراضي ومباني", "Land & Buildings", "Tanah & Bangunan"),
        "code": "FA-BLD",
        "method": "STRAIGHT_LINE",
        "useful_life": 240,
        "salvage_pct": Decimal("10.00"),
        "asset_acct": "1610",
        "depr_exp_acct": "6400",
        "accum_depr_acct": "1710",
        "disposal_gain_acct": "4300",
        "disposal_loss_acct": "6800",
        "acq_source_acct": "1020",
        "disposal_proceeds_acct": "1020",
        "reval_surplus_acct": "3200",
    },
    {
        "name": _t("أثاث ومعدات", "Furniture & Equipment", "Perabot & Peralatan"),
        "code": "FA-FRN",
        "method": "STRAIGHT_LINE",
        "useful_life": 60,
        "salvage_pct": Decimal("5.00"),
        "asset_acct": "1620",
        "depr_exp_acct": "6400",
        "accum_depr_acct": "1720",
        "disposal_gain_acct": "4300",
        "disposal_loss_acct": "6800",
        "acq_source_acct": "1020",
        "disposal_proceeds_acct": "1020",
        "reval_surplus_acct": "3200",
    },
    {
        "name": _t("مركبات", "Vehicles", "Kendaraan"),
        "code": "FA-VEH",
        "method": "DECLINING_BALANCE",
        "useful_life": 60,
        "salvage_pct": Decimal("10.00"),
        "asset_acct": "1630",
        "depr_exp_acct": "6400",
        "accum_depr_acct": "1730",
        "disposal_gain_acct": "4300",
        "disposal_loss_acct": "6800",
        "acq_source_acct": "1020",
        "disposal_proceeds_acct": "1010",
        "reval_surplus_acct": "3200",
    },
    {
        "name": _t("معدات تقنية وبرمجيات", "IT Equipment & Software", "Peralatan IT & Perangkat Lunak"),
        "code": "FA-IT",
        "method": "STRAIGHT_LINE",
        "useful_life": 36,
        "salvage_pct": Decimal("0.00"),
        "asset_acct": "1640",
        "depr_exp_acct": "6400",
        "accum_depr_acct": "1740",
        "disposal_gain_acct": "4300",
        "disposal_loss_acct": "6800",
        "acq_source_acct": "1020",
        "disposal_proceeds_acct": "1010",
        "reval_surplus_acct": "3200",
    },
    {
        "name": _t("تحسينات مباني مستأجرة", "Leasehold Improvements", "Perbaikan Sewa"),
        "code": "FA-LHI",
        "method": "STRAIGHT_LINE",
        "useful_life": 120,
        "salvage_pct": Decimal("0.00"),
        "asset_acct": "1650",
        "depr_exp_acct": "6400",
        "accum_depr_acct": "1750",
        "disposal_gain_acct": "4300",
        "disposal_loss_acct": "6800",
        "acq_source_acct": "1020",
        "disposal_proceeds_acct": "1020",
        "reval_surplus_acct": "3200",
    },
]


# =============================================================================
# Sequences
# =============================================================================

SEQUENCES = [
    ("INVOICE", "INV-"),
    ("PAYMENT", "PAY-"),
    ("EXPENSE", "EXP-"),
    ("QUOTATION", "QUO-"),
    ("PURCHASE_ORDER", "PO-"),
    ("EMPLOYEE", "EMP-"),
    ("CUSTOMER", "CUS-"),
    ("SUPPLIER", "SUP-"),
]


# =============================================================================
# System Settings
# =============================================================================

TIMEZONES_BY_CURRENCY = {
    "SAR": "Asia/Riyadh",
    "AED": "Asia/Dubai",
    "KWD": "Asia/Kuwait",
    "QAR": "Asia/Qatar",
    "BHD": "Asia/Bahrain",
    "OMR": "Asia/Muscat",
    "JOD": "Asia/Amman",
    "EGP": "Africa/Cairo",
    "USD": "America/New_York",
    "EUR": "Europe/Berlin",
    "GBP": "Europe/London",
    "IDR": "Asia/Jakarta",
}


def get_default_timezone(currency_code: str) -> str:
    return TIMEZONES_BY_CURRENCY.get(currency_code, "UTC")


# =============================================================================
# HQ Branch Name
# =============================================================================

HQ_BRANCH_NAME = _t("المقر الرئيسي", "Headquarters", "Kantor Pusat")


# =============================================================================
# Fiscal Year Default Name
# =============================================================================


def get_default_fiscal_year_name(year: int, lang: str = "ar") -> str:
    names = {
        "ar": f"السنة المالية {year}",
        "en": f"Fiscal Year {year}",
        "id": f"Tahun Fiskal {year}",
    }
    return names.get(lang, names["en"])


# =============================================================================
# Chart Preset Choices
# =============================================================================

CHART_PRESET_CHOICES_DATA = [
    ("standard", _t("الدليل المحاسبي القياسي", "Standard Chart of Accounts", "Bagan Akun Standar")),
    ("travel_agency", _t("دليل وكالات السفر", "Travel Agency Chart", "Bagan Akun Agen Perjalanan")),
    ("services", _t("دليل شركات الخدمات", "Services Company Chart", "Bagan Akun Perusahaan Jasa")),
    ("minimal", _t("دليل مبسط", "Minimal Chart", "Bagan Akun Sederhana")),
]


def get_chart_preset_choices(lang: str = "ar") -> list:
    return [(key, get_text(label, lang)) for key, label in CHART_PRESET_CHOICES_DATA]


# =============================================================================
# Fiscal Year Start Month Choices
# =============================================================================

FISCAL_START_MONTHS = [
    (1, _t("يناير (السنة الميلادية)", "January (Calendar Year)", "Januari (Tahun Kalender)")),
    (4, _t("أبريل", "April", "April")),
    (7, _t("يوليو", "July", "Juli")),
    (10, _t("أكتوبر", "October", "Oktober")),
]


def get_fiscal_start_choices(lang: str = "ar") -> list:
    return [(val, get_text(label, lang)) for val, label in FISCAL_START_MONTHS]


# =============================================================================
# Country Defaults
# =============================================================================

DEFAULT_COUNTRY = _t("المملكة العربية السعودية", "Saudi Arabia", "Arab Saudi")


# =============================================================================
# UI Messages
# =============================================================================

SETUP_SUCCESS_MSG = _t(
    "تم إعداد النظام بنجاح! مرحباً بك في نظام إدارة المؤسسات.",
    "System setup completed successfully! Welcome to the Enterprise Management System.",
    "Pengaturan sistem berhasil! Selamat datang di Sistem Manajemen Perusahaan.",
)

SETUP_ERROR_MSG = _t(
    "حدث خطأ أثناء الإعداد: ",
    "An error occurred during setup: ",
    "Terjadi kesalahan saat pengaturan: ",
)
