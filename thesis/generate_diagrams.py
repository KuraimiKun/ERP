"""
Generate all thesis diagrams as high-quality PNG images.
Run: python thesis/generate_diagrams.py
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
import os

OUT = os.path.join(os.path.dirname(__file__), 'figures')
os.makedirs(OUT, exist_ok=True)

# ── Colour palette ──────────────────────────────────────────────
C = {
    'primary':   '#2563EB',   # blue-600
    'secondary': '#7C3AED',   # violet-600
    'accent':    '#059669',   # emerald-600
    'warning':   '#D97706',   # amber-600
    'danger':    '#DC2626',   # red-600
    'gray':      '#6B7280',   # gray-500
    'light':     '#F3F4F6',   # gray-100
    'bg':        '#FFFFFF',
    'dark':      '#1F2937',   # gray-800
    'blue_l':    '#DBEAFE',
    'violet_l':  '#EDE9FE',
    'green_l':   '#D1FAE5',
    'amber_l':   '#FEF3C7',
    'red_l':     '#FEE2E2',
    'slate_l':   '#F1F5F9',
}

def save(fig, name):
    path = os.path.join(OUT, f'{name}.png')
    fig.savefig(path, dpi=300, bbox_inches='tight', facecolor='white', pad_inches=0.3)
    plt.close(fig)
    print(f'  ✓ {path}')


# ═══════════════════════════════════════════════════════════════
#  1. ERP EVOLUTION TIMELINE
# ═══════════════════════════════════════════════════════════════
def fig_erp_evolution():
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.set_xlim(-0.5, 5.5)
    ax.set_ylim(-1.5, 2.5)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    eras = [
        ('1970s',   'MRP',               'Material Requirements\nPlanning',         C['gray'],      C['slate_l']),
        ('1980s',   'MRP II',            'Manufacturing Resource\nPlanning',         C['warning'],   C['amber_l']),
        ('1990s',   'ERP',               'Enterprise Resource\nPlanning (SAP R/3)', C['primary'],   C['blue_l']),
        ('2000s',   'Extended ERP',      'SCM, CRM, BI\nIntegration',               C['secondary'], C['violet_l']),
        ('2010s',   'Cloud ERP',         'SaaS, Multi-Tenant\nMobile Access',       C['accent'],    C['green_l']),
        ('2020s',   'AI-Enhanced ERP',   'ML/AI, Predictive\nAnalytics (This Project)', C['danger'], C['red_l']),
    ]

    # Draw timeline arrow
    ax.annotate('', xy=(5.3, 0), xytext=(-0.3, 0),
                arrowprops=dict(arrowstyle='->', color=C['dark'], lw=2.5))

    for i, (year, title, desc, color, bg) in enumerate(eras):
        # Node circle
        circle = plt.Circle((i, 0), 0.28, color=color, zorder=5)
        ax.add_patch(circle)
        ax.text(i, 0, year[:2]+'\n'+year[2:], ha='center', va='center',
                fontsize=7, fontweight='bold', color='white', zorder=6)

        # Alternating above/below
        if i % 2 == 0:
            y_box, y_line = 1.4, 0.35
            _va = 'bottom'
        else:
            y_box, y_line = -1.4, -0.35
            _va = 'top'

        # Connector line
        ax.plot([i, i], [y_line, y_box - (0.4 if i % 2 == 0 else -0.4)],
                color=color, lw=1.5, ls='--', alpha=0.6)

        # Info box
        bbox = dict(boxstyle='round,pad=0.4', facecolor=bg, edgecolor=color, lw=1.5)
        ax.text(i, y_box, f'{title}\n\n{desc}', ha='center', va='center',
                fontsize=8, fontweight='bold', color=C['dark'], bbox=bbox)

    ax.set_title('Evolution of ERP Systems', fontsize=16, fontweight='bold',
                 color=C['dark'], pad=20)
    save(fig, 'erp_evolution_timeline')


# ═══════════════════════════════════════════════════════════════
#  2. MULTI-TENANCY MODELS
# ═══════════════════════════════════════════════════════════════
def fig_multi_tenancy():
    fig, axes = plt.subplots(1, 3, figsize=(16, 6))
    fig.patch.set_facecolor('white')

    models = [
        {
            'title': 'Model 1: Shared DB\nShared Schema',
            'isolation': 'Low',
            'iso_color': C['danger'],
            'tables': [
                ('Customers', ['T1: Acme Corp', 'T2: Beta Inc', 'T1: Acme Ltd']),
            ],
            'highlight': 'tenant_id column\nfilters data',
            'db_count': 1,
        },
        {
            'title': 'Model 2: Shared DB\nSeparate Schema',
            'isolation': 'Medium',
            'iso_color': C['warning'],
            'tables': [
                ('Schema: tenant_1', ['Customers', 'Invoices', 'Products']),
                ('Schema: tenant_2', ['Customers', 'Invoices', 'Products']),
            ],
            'highlight': 'PostgreSQL schemas\nwithin one DB',
            'db_count': 1,
        },
        {
            'title': 'Model 3: Separate\nDatabase (This Project)',
            'isolation': 'High ✓',
            'iso_color': C['accent'],
            'tables': [
                ('DB: tenant_1_db', ['All 80+ tables']),
                ('DB: tenant_2_db', ['All 80+ tables']),
                ('DB: tenant_3_db', ['All 80+ tables']),
            ],
            'highlight': 'Complete physical\nisolation per tenant',
            'db_count': 3,
        },
    ]

    for idx, (ax, model) in enumerate(zip(axes, models)):
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.axis('off')

        # Title
        ax.text(5, 9.5, model['title'], ha='center', va='top',
                fontsize=11, fontweight='bold', color=C['dark'])

        # Isolation badge
        badge_color = model['iso_color']
        bbox = dict(boxstyle='round,pad=0.3', facecolor=badge_color, edgecolor='none')
        ax.text(5, 8.2, f"Isolation: {model['isolation']}", ha='center', va='center',
                fontsize=10, fontweight='bold', color='white', bbox=bbox)

        # Database boxes
        y_start = 7.0
        for i, (tbl_name, rows) in enumerate(model['tables']):
            y = y_start - i * 2.2
            box = FancyBboxPatch((1, y - 1.5), 8, 1.8,
                                  boxstyle='round,pad=0.15',
                                  facecolor=C['blue_l'], edgecolor=C['primary'], lw=1.5)
            ax.add_patch(box)
            ax.text(5, y, tbl_name, ha='center', va='top',
                    fontsize=9, fontweight='bold', color=C['primary'])
            for j, row in enumerate(rows):
                ax.text(5, y - 0.5 - j * 0.4, row, ha='center', va='top',
                        fontsize=8, color=C['dark'])

        # Highlight text
        bbox2 = dict(boxstyle='round,pad=0.3', facecolor=C['amber_l'], edgecolor=C['warning'], lw=1)
        ax.text(5, 0.8, model['highlight'], ha='center', va='center',
                fontsize=8.5, fontstyle='italic', color=C['dark'], bbox=bbox2)

    fig.suptitle('Multi-Tenant Data Isolation Models', fontsize=16, fontweight='bold',
                 color=C['dark'], y=1.02)
    fig.tight_layout()
    save(fig, 'multi_tenancy_models')


# ═══════════════════════════════════════════════════════════════
#  3. SPRINT LIFECYCLE DIAGRAM
# ═══════════════════════════════════════════════════════════════
def fig_sprint_lifecycle():
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_xlim(-6, 6)
    ax.set_ylim(-6, 6)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    # Central circle
    circle = plt.Circle((0, 0), 1.6, color=C['primary'], zorder=5)
    ax.add_patch(circle)
    ax.text(0, 0.2, 'SPRINT', ha='center', va='center',
            fontsize=18, fontweight='bold', color='white', zorder=6)
    ax.text(0, -0.4, '2 Weeks', ha='center', va='center',
            fontsize=11, color='white', zorder=6, alpha=0.9)

    # Phases around the circle
    phases = [
        (90,   'Sprint\nPlanning',    'Define backlog items\n& acceptance criteria',  C['secondary'], C['violet_l']),
        (18,   'Development',         'Code, integrate\n& build features',           C['primary'],   C['blue_l']),
        (-54,  'Testing',             'Unit tests, ML model\nevaluation, QA',         C['accent'],    C['green_l']),
        (-126, 'Sprint\nReview',      'Demo to supervisor\n& stakeholders',           C['warning'],   C['amber_l']),
        (-198, 'Sprint\nRetrospective','Lessons learned\n& process improvement',      C['danger'],    C['red_l']),
    ]

    radius = 4.0
    for angle_deg, title, desc, color, bg in phases:
        angle = np.radians(angle_deg)
        x = radius * np.cos(angle)
        y = radius * np.sin(angle)

        # Connector from center to phase
        x_inner = 1.8 * np.cos(angle)
        y_inner = 1.8 * np.sin(angle)
        ax.annotate('', xy=(x - 0.0 * np.cos(angle), y - 0.0 * np.sin(angle)),
                    xytext=(x_inner, y_inner),
                    arrowprops=dict(arrowstyle='->', color=color, lw=2, connectionstyle='arc3,rad=0.0'))

        # Phase box
        bbox = dict(boxstyle='round,pad=0.5', facecolor=bg, edgecolor=color, lw=2)
        ax.text(x, y + 0.3, title, ha='center', va='center',
                fontsize=11, fontweight='bold', color=color, bbox=bbox)
        ax.text(x, y - 0.7, desc, ha='center', va='center',
                fontsize=8, color=C['dark'])

    # Curved arrows between phases (clockwise)
    for i in range(len(phases)):
        a1 = np.radians(phases[i][0])
        a2 = np.radians(phases[(i + 1) % len(phases)][0])
        # Draw arc
        if i == len(phases) - 1:
            pass
        arc_r = 2.5
        ax.annotate('', xy=(arc_r * np.cos(a2 + 0.15), arc_r * np.sin(a2 + 0.15)),
                    xytext=(arc_r * np.cos(a1 - 0.15), arc_r * np.sin(a1 - 0.15)),
                    arrowprops=dict(arrowstyle='->', color=C['gray'], lw=1.5,
                                    connectionstyle='arc3,rad=0.4', alpha=0.5))

    # Input / Output labels
    bbox_in = dict(boxstyle='round,pad=0.3', facecolor=C['green_l'], edgecolor=C['accent'], lw=1.5)
    ax.text(-5.5, 5, 'Input:\nProduct Backlog', ha='center', va='center',
            fontsize=9, fontweight='bold', color=C['accent'], bbox=bbox_in)
    ax.annotate('', xy=(-3.5, 3.8), xytext=(-5, 4.4),
                arrowprops=dict(arrowstyle='->', color=C['accent'], lw=1.5))

    bbox_out = dict(boxstyle='round,pad=0.3', facecolor=C['amber_l'], edgecolor=C['warning'], lw=1.5)
    ax.text(5.5, -5, 'Output:\nWorking Increment\n+ Updated Backlog', ha='center', va='center',
            fontsize=9, fontweight='bold', color=C['warning'], bbox=bbox_out)
    ax.annotate('', xy=(5, -4.4), xytext=(3.5, -3.8),
                arrowprops=dict(arrowstyle='->', color=C['warning'], lw=1.5))

    ax.set_title('Sprint (Agile) Methodology Lifecycle', fontsize=16, fontweight='bold',
                 color=C['dark'], pad=20)
    save(fig, 'sprint_lifecycle')


# ═══════════════════════════════════════════════════════════════
#  4. SPRINT GANTT CHART
# ═══════════════════════════════════════════════════════════════
def fig_gantt():
    fig, ax = plt.subplots(figsize=(14, 6))
    fig.patch.set_facecolor('white')

    sprints = [
        ('Sprint 1: Multi-Tenant Architecture',         0,  2, C['primary'],   C['blue_l']),
        ('Sprint 2: Finance & HR Modules',               2,  2, C['secondary'], C['violet_l']),
        ('Sprint 3: CRM, Supplier & Procurement',        4,  2, C['accent'],    C['green_l']),
        ('Sprint 4: Inventory/WMS & POS',                6,  2, C['warning'],   C['amber_l']),
        ('Sprint 5: ML Model Development',               8,  2, C['danger'],    C['red_l']),
        ('Sprint 6: Data Integration & ML Tuning',      10,  2, C['primary'],   C['blue_l']),
        ('Sprint 7: Testing, Docs & Deployment',        12,  2, C['secondary'], C['violet_l']),
    ]

    n = len(sprints)
    for i, (label, start, dur, color, bg) in enumerate(sprints):
        y = n - i - 1
        # Bar
        ax.barh(y, dur, left=start, height=0.6, color=bg, edgecolor=color, lw=2, zorder=3)
        # Label inside bar
        ax.text(start + dur / 2, y, f'Weeks {start+1}–{start+dur}', ha='center', va='center',
                fontsize=9, fontweight='bold', color=color, zorder=4)

    # Y labels
    ax.set_yticks(range(n))
    ax.set_yticklabels([s[0] for s in reversed(sprints)], fontsize=10, fontweight='bold', color=C['dark'])

    # X axis
    ax.set_xlim(-0.5, 15)
    ax.set_xticks(range(0, 15, 2))
    ax.set_xticklabels([f'Week {w}' if w > 0 else 'Start' for w in range(0, 15, 2)],
                        fontsize=9, color=C['gray'])
    ax.set_xlabel('Project Timeline', fontsize=11, fontweight='bold', color=C['dark'])

    # Grid
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, color=C['light'], lw=1)
    ax.yaxis.grid(False)

    # Remove spines
    for spine in ['top', 'right', 'bottom']:
        ax.spines[spine].set_visible(False)
    ax.spines['left'].set_color(C['light'])

    # Milestone markers
    milestones = [
        (2,  '✓ Tenant\nIsolation'),
        (6,  '✓ Core ERP\nModules'),
        (10, '✓ 8 ML\nModels'),
        (14, '✓ Production\nReady'),
    ]
    for mx, mlabel in milestones:
        ax.axvline(x=mx, color=C['danger'], lw=1, ls=':', alpha=0.5, zorder=1)
        ax.text(mx, n + 0.1, mlabel, ha='center', va='bottom',
                fontsize=8, fontweight='bold', color=C['danger'])

    ax.set_ylim(-0.5, n + 1)
    ax.set_title('Sprint Gantt Chart — Project Timeline', fontsize=16, fontweight='bold',
                 color=C['dark'], pad=25)
    fig.tight_layout()
    save(fig, 'sprint_gantt_chart')


# ═══════════════════════════════════════════════════════════════
#  5. SYSTEM ARCHITECTURE DIAGRAM
# ═══════════════════════════════════════════════════════════════
def _draw_box(ax, x, y, w, h, text, color, bg, fontsize=9, bold=True):
    box = FancyBboxPatch((x - w/2, y - h/2), w, h,
                          boxstyle='round,pad=0.12', facecolor=bg, edgecolor=color, lw=1.8)
    ax.add_patch(box)
    weight = 'bold' if bold else 'normal'
    ax.text(x, y, text, ha='center', va='center', fontsize=fontsize,
            fontweight=weight, color=color, zorder=5)
    return (x, y)


def fig_system_architecture():
    fig, ax = plt.subplots(figsize=(16, 12))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 12)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    # ── Layer 1: Presentation / Client ─────────────────────────
    layer_y = 11
    bbox_layer = dict(boxstyle='round,pad=0.2', facecolor=C['blue_l'], edgecolor=C['primary'], lw=1)
    ax.text(0.5, layer_y, 'PRESENTATION LAYER', fontsize=8, fontweight='bold',
            color=C['primary'], bbox=bbox_layer, va='center')

    _draw_box(ax, 4,  layer_y, 2.5, 0.7, 'Web Browser\n(Django Templates)', C['primary'], C['blue_l'], 8)
    _draw_box(ax, 7.5, layer_y, 2.5, 0.7, 'Mobile / SPA\n(REST API Client)', C['primary'], C['blue_l'], 8)
    _draw_box(ax, 11, layer_y, 2.5, 0.7, 'Third-Party\nIntegrations', C['primary'], C['blue_l'], 8)

    # ── Layer 2: Application (Django) ──────────────────────────
    layer_y = 9
    ax.text(0.5, layer_y + 0.6, 'APPLICATION LAYER (Django 4.2)', fontsize=8, fontweight='bold',
            color=C['secondary'], bbox=dict(boxstyle='round,pad=0.2', facecolor=C['violet_l'],
            edgecolor=C['secondary'], lw=1), va='center')

    # Middleware bar
    _draw_box(ax, 8, layer_y + 0.6, 10, 0.5, 'Authentication Middleware  →  Tenant Database Routing Middleware  →  CSRF / Security Middleware',
              C['gray'], C['slate_l'], 8, False)

    modules = [
        ('Finance\nModule', 2.5),
        ('HR\nModule', 4.5),
        ('CRM\nModule', 6.5),
        ('Inventory\n& WMS', 8.5),
        ('Suppliers\nModule', 10.5),
        ('POS\nModule', 12.5),
    ]
    for label, x in modules:
        _draw_box(ax, x, layer_y - 0.6, 1.7, 0.7, label, C['secondary'], C['violet_l'], 7.5)

    # AI module (highlighted)
    _draw_box(ax, 14.5, layer_y - 0.6, 1.7, 0.7, '[AI/ML]\nModule', C['danger'], C['red_l'], 7.5)

    # ── Layer 3: Services ──────────────────────────────────────
    layer_y = 7.2
    ax.text(0.5, layer_y + 0.3, 'SERVICE LAYER', fontsize=8, fontweight='bold',
            color=C['accent'], bbox=dict(boxstyle='round,pad=0.2', facecolor=C['green_l'],
            edgecolor=C['accent'], lw=1), va='center')

    services = [
        ('Django REST\nFramework API', 3.5),
        ('ML Training\nPipeline', 6.5),
        ('AI Insight\nEngine', 9),
        ('Celery + Redis\nTask Queue', 11.5),
        ('Notification\nService', 14),
    ]
    for label, x in services:
        _draw_box(ax, x, layer_y - 0.3, 2, 0.65, label, C['accent'], C['green_l'], 8)

    # ── Layer 4: Data ──────────────────────────────────────────
    layer_y = 5.0
    ax.text(0.5, layer_y + 0.3, 'DATA LAYER', fontsize=8, fontweight='bold',
            color=C['warning'], bbox=dict(boxstyle='round,pad=0.2', facecolor=C['amber_l'],
            edgecolor=C['warning'], lw=1), va='center')

    # Main DB
    _draw_box(ax, 3, layer_y - 0.5, 3.5, 1.2,
              'Main Database\n(erp_main)\n\nTenantUser, PostgresServer\nTenantDatabase, DatabaseAssignment',
              C['warning'], C['amber_l'], 7.5)

    # Tenant DBs
    _draw_box(ax, 8, layer_y - 0.5, 2.3, 1.2, 'Tenant DB 1\n\n80+ Domain\nModels', C['primary'], C['blue_l'], 7.5)
    _draw_box(ax, 10.8, layer_y - 0.5, 2.3, 1.2, 'Tenant DB 2\n\n80+ Domain\nModels', C['primary'], C['blue_l'], 7.5)
    _draw_box(ax, 13.6, layer_y - 0.5, 2.3, 1.2, 'Tenant DB N\n\n80+ Domain\nModels', C['primary'], C['blue_l'], 7.5)

    # Ellipsis
    ax.text(12.2, layer_y - 0.5, '...', fontsize=18, ha='center', va='center', color=C['gray'])

    # ── Layer 5: Infrastructure ────────────────────────────────
    layer_y = 2.5
    ax.text(0.5, layer_y + 0.3, 'INFRASTRUCTURE', fontsize=8, fontweight='bold',
            color=C['gray'], bbox=dict(boxstyle='round,pad=0.2', facecolor=C['slate_l'],
            edgecolor=C['gray'], lw=1), va='center')

    _draw_box(ax, 4, layer_y - 0.3, 3.5, 0.7, 'Docker Containers\n(PostgreSQL Servers)', C['gray'], C['slate_l'], 8)
    _draw_box(ax, 8.5, layer_y - 0.3, 3, 0.7, 'Remote PostgreSQL\nServers', C['gray'], C['slate_l'], 8)
    _draw_box(ax, 12.5, layer_y - 0.3, 3, 0.7, 'ML Model Artifacts\n(Joblib / Pickle)', C['gray'], C['slate_l'], 8)

    # ── Arrows between layers ─────────────────────────────────
    for x in [4, 7.5, 11]:
        ax.annotate('', xy=(x, 10.2), xytext=(x, 10.55),
                    arrowprops=dict(arrowstyle='->', color=C['gray'], lw=1.2))

    for x in [3.5, 6.5, 9, 11.5, 14]:
        ax.annotate('', xy=(x, 6.55), xytext=(x, 7.75),
                    arrowprops=dict(arrowstyle='<->', color=C['gray'], lw=1, alpha=0.5))

    ax.set_title('System Architecture — AI-Enhanced Multi-Tenant ERP',
                 fontsize=16, fontweight='bold', color=C['dark'], pad=15)
    save(fig, 'system_architecture')


# ═══════════════════════════════════════════════════════════════
#  6. MULTI-TENANT ARCHITECTURE
# ═══════════════════════════════════════════════════════════════
def fig_multi_tenant_arch():
    fig, ax = plt.subplots(figsize=(15, 10))
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 10)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    # ── Users ──────────────────────────────────────────────────
    users = [
        ('User A\n(Org Alpha)', 2.5, 9),
        ('User B\n(Org Beta)',  7.5, 9),
        ('User C\n(Org Gamma)', 12.5, 9),
    ]
    for label, x, y in users:
        _draw_box(ax, x, y, 2.5, 0.8, label, C['primary'], C['blue_l'], 9)

    # ── Django Application (shared) ────────────────────────────
    box = FancyBboxPatch((1, 5.5), 13, 2.5, boxstyle='round,pad=0.2',
                          facecolor=C['violet_l'], edgecolor=C['secondary'], lw=2)
    ax.add_patch(box)
    ax.text(7.5, 7.65, 'Django Application (Single Instance)', ha='center', va='center',
            fontsize=13, fontweight='bold', color=C['secondary'])

    # Inside Django box
    components = [
        ('Authentication\n& User Approval', 3, 6.6),
        ('Tenant Database\nRouter', 6, 6.6),
        ('TenantDB\nContext Manager', 9, 6.6),
        ('Role-Based\nAccess Control', 12, 6.6),
    ]
    for label, x, y in components:
        _draw_box(ax, x, y, 2.3, 0.8, label, C['secondary'], 'white', 8)

    # ── Arrows from users to Django ────────────────────────────
    for _, x, _ in users:
        ax.annotate('', xy=(x, 8.1), xytext=(x, 8.5),
                    arrowprops=dict(arrowstyle='->', color=C['primary'], lw=2))
        ax.text(x, 8.35, 'HTTPS', ha='center', va='center', fontsize=7, color=C['gray'])

    # ── Database Router Arrow ──────────────────────────────────
    ax.annotate('', xy=(7.5, 4.8), xytext=(7.5, 5.4),
                arrowprops=dict(arrowstyle='->', color=C['warning'], lw=2.5))
    ax.text(7.5, 5.1, 'Dynamic\nRouting', ha='center', va='center', fontsize=8,
            fontweight='bold', color=C['warning'])

    # ── Main Database ──────────────────────────────────────────
    _draw_box(ax, 2.5, 4, 3.5, 1.2,
              'Main DB (erp_main)\n\nTenantUser\nPostgresServer\nTenantDatabase\nDatabaseAssignment',
              C['warning'], C['amber_l'], 7.5)

    # ── Tenant Databases ───────────────────────────────────────
    tenant_dbs = [
        ('Alpha DB\n\nFinance, HR, CRM\nInventory, POS\n+ ML Models', 7, C['primary']),
        ('Beta DB\n\nFinance, HR, CRM\nInventory, POS\n+ ML Models', 10, C['accent']),
        ('Gamma DB\n\nFinance, HR, CRM\nInventory, POS\n+ ML Models', 13, C['secondary']),
    ]
    for label, x, color in tenant_dbs:
        bg = C['blue_l'] if color == C['primary'] else (C['green_l'] if color == C['accent'] else C['violet_l'])
        _draw_box(ax, x, 4, 2.5, 1.5, label, color, bg, 7.5)

    # ── Docker / Remote Servers ────────────────────────────────
    _draw_box(ax, 5, 1.5, 4, 0.8, 'Docker PostgreSQL Container\n(Auto-provisioned)', C['gray'], C['slate_l'], 8)
    _draw_box(ax, 11, 1.5, 4.5, 0.8, 'Remote PostgreSQL Server\n(Manual connection)', C['gray'], C['slate_l'], 8)

    # Arrows to servers
    ax.annotate('', xy=(5, 2.0), xytext=(5, 3.15),
                arrowprops=dict(arrowstyle='->', color=C['gray'], lw=1.5))
    ax.annotate('', xy=(11, 2.0), xytext=(11, 3.15),
                arrowprops=dict(arrowstyle='->', color=C['gray'], lw=1.5))

    # ── Data Isolation Badge ───────────────────────────────────
    bbox = dict(boxstyle='round,pad=0.4', facecolor=C['green_l'], edgecolor=C['accent'], lw=2)
    ax.text(7.5, 0.5, 'Complete Data Isolation — Each Organisation Gets Its Own PostgreSQL Database',
            ha='center', va='center', fontsize=10, fontweight='bold', color=C['accent'], bbox=bbox)

    ax.set_title('Multi-Tenant Database Architecture', fontsize=16, fontweight='bold',
                 color=C['dark'], pad=15)
    save(fig, 'multi_tenant_architecture')


# ═══════════════════════════════════════════════════════════════
#  7. ML PIPELINE ARCHITECTURE
# ═══════════════════════════════════════════════════════════════
def fig_ml_pipeline():
    fig, ax = plt.subplots(figsize=(16, 11))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 11)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    # ── Stage 1: Data Sources ──────────────────────────────────
    ax.text(0.5, 10.3, '① DATA SOURCES', fontsize=10, fontweight='bold', color=C['primary'])

    sources = [
        ('Invoices &\nPayments', 2),
        ('Employees &\nAttendance', 4.5),
        ('Leads &\nCRM Activity', 7),
        ('Stock Movements\n& Inventory', 9.5),
        ('Expense\nClaims', 12),
        ('KPI Daily\nMetrics', 14.5),
    ]
    for label, x in sources:
        _draw_box(ax, x, 9.5, 2, 0.7, label, C['primary'], C['blue_l'], 8)

    # ── Arrow down ─────────────────────────────────────────────
    ax.annotate('', xy=(8, 8.7), xytext=(8, 9.0),
                arrowprops=dict(arrowstyle='->', color=C['dark'], lw=2))

    # ── Stage 2: Feature Engineering ───────────────────────────
    ax.text(0.5, 8.5, '② FEATURE ENGINEERING', fontsize=10, fontweight='bold', color=C['secondary'])

    features = [
        ('Numerical\nScaling', 3),
        ('Categorical\nEncoding', 6),
        ('Temporal\nFeatures', 9),
        ('Leakage-Free\nStatistics', 12),
        ('Time-Series\nResampling', 15),
    ]

    feat_box = FancyBboxPatch((1.5, 7.4), 14, 0.9, boxstyle='round,pad=0.15',
                               facecolor=C['violet_l'], edgecolor=C['secondary'], lw=1.5)
    ax.add_patch(feat_box)
    for label, x in features:
        ax.text(x, 7.85, label, ha='center', va='center', fontsize=8,
                fontweight='bold', color=C['secondary'])

    # ── Arrow down ─────────────────────────────────────────────
    ax.annotate('', xy=(8, 7.0), xytext=(8, 7.3),
                arrowprops=dict(arrowstyle='->', color=C['dark'], lw=2))

    # ── Stage 3: ML Models ─────────────────────────────────────
    ax.text(0.5, 6.8, '③ ML MODELS (8 Models)', fontsize=10, fontweight='bold', color=C['accent'])

    models_row1 = [
        ('Lead Scoring\nLogistic Regression', 2.5, C['primary']),
        ('Late Payment\nGradient Boosting', 5.5, C['secondary']),
        ('Attrition Risk\nRandom Forest', 8.5, C['accent']),
        ('Expense Anomaly\nIsolation Forest', 11.5, C['warning']),
    ]
    models_row2 = [
        ('Attendance\nZ-Score Analysis', 2.5, C['danger']),
        ('Demand Forecast\nFacebook Prophet', 5.5, C['primary']),
        ('Cash Flow\nRule-Based Model', 8.5, C['secondary']),
        ('KPI Anomaly\nStatistical Control', 11.5, C['accent']),
    ]

    model_box = FancyBboxPatch((1, 4.6), 12, 2.2, boxstyle='round,pad=0.15',
                                facecolor=C['green_l'], edgecolor=C['accent'], lw=1.5, alpha=0.3)
    ax.add_patch(model_box)

    for label, x, color in models_row1:
        _draw_box(ax, x, 6.2, 2.5, 0.65, label, color, 'white', 7.5)
    for label, x, color in models_row2:
        _draw_box(ax, x, 5.2, 2.5, 0.65, label, color, 'white', 7.5)

    # ── Model Registry (side) ─────────────────────────────────
    _draw_box(ax, 14.5, 5.7, 2.2, 1.8, 'Model\nRegistry\n\n(MLModel)\nVersion\nAccuracy\nJoblib Path', C['gray'], C['slate_l'], 7.5)
    ax.annotate('', xy=(13.3, 5.7), xytext=(13, 5.7),
                arrowprops=dict(arrowstyle='<->', color=C['gray'], lw=1.5))

    # ── Arrow down ─────────────────────────────────────────────
    ax.annotate('', xy=(7, 4.2), xytext=(7, 4.5),
                arrowprops=dict(arrowstyle='->', color=C['dark'], lw=2))

    # ── Stage 4: Evaluation ────────────────────────────────────
    ax.text(0.5, 4.1, '④ EVALUATION', fontsize=10, fontweight='bold', color=C['warning'])

    eval_box = FancyBboxPatch((1.5, 3.2), 14, 0.8, boxstyle='round,pad=0.15',
                               facecolor=C['amber_l'], edgecolor=C['warning'], lw=1.5)
    ax.add_patch(eval_box)

    evals = [
        ('AUC-ROC\n0.6766 — 0.9867', 3.5),
        ('F1-Score\n(Anomaly)', 6.5),
        ('MAE Accuracy\n0.7249 (Prophet CV)', 9.5),
        ('Z-Score\nCalibration', 12.5),
    ]
    for label, x in evals:
        ax.text(x, 3.6, label, ha='center', va='center', fontsize=8,
                fontweight='bold', color=C['warning'])

    # ── Arrow down ─────────────────────────────────────────────
    ax.annotate('', xy=(8, 2.8), xytext=(8, 3.1),
                arrowprops=dict(arrowstyle='->', color=C['dark'], lw=2))

    # ── Stage 5: AI Insight Engine ─────────────────────────────
    ax.text(0.5, 2.6, '⑤ AI INSIGHT ENGINE', fontsize=10, fontweight='bold', color=C['danger'])

    insight_box = FancyBboxPatch((1.5, 1.4), 13.5, 1.1, boxstyle='round,pad=0.15',
                                  facecolor=C['red_l'], edgecolor=C['danger'], lw=2)
    ax.add_patch(insight_box)

    insights = [
        ('Generate\nAIInsight', 3.5),
        ('Severity:\nInfo / Warning\n/ Critical', 6.5),
        ('Prediction\nLog (Audit)', 9.5),
        ('Notify\nCompany Users', 12.5),
    ]
    for label, x in insights:
        ax.text(x, 1.95, label, ha='center', va='center', fontsize=8,
                fontweight='bold', color=C['danger'])

    # ── Output ─────────────────────────────────────────────────
    bbox_out = dict(boxstyle='round,pad=0.4', facecolor=C['green_l'], edgecolor=C['accent'], lw=2)
    ax.text(8, 0.5, 'Actionable Business Insights delivered to ERP Dashboard & Notifications',
            ha='center', va='center', fontsize=10, fontweight='bold', color=C['accent'], bbox=bbox_out)
    ax.annotate('', xy=(8, 0.85), xytext=(8, 1.3),
                arrowprops=dict(arrowstyle='->', color=C['accent'], lw=2))

    ax.set_title('AI/ML Pipeline Architecture', fontsize=16, fontweight='bold',
                 color=C['dark'], pad=15)
    save(fig, 'ml_pipeline_architecture')


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print('Generating thesis diagrams...\n')
    fig_erp_evolution()
    fig_multi_tenancy()
    fig_sprint_lifecycle()
    fig_gantt()
    fig_system_architecture()
    fig_multi_tenant_arch()
    fig_ml_pipeline()
    print(f'\nAll 7 diagrams saved to: {OUT}/')
