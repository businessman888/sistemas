import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Form

from app.core.database import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard/panel", tags=["dashboard_panel"])


def parse_float(val, default=0.0) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if not val:
        return default
    val_str = str(val).replace('R$', '').replace(' ', '').strip()
    if ',' in val_str and '.' in val_str:
        if val_str.rfind(',') > val_str.rfind('.'):
            val_str = val_str.replace('.', '').replace(',', '.')
        else:
            val_str = val_str.replace(',', '')
    elif ',' in val_str:
        val_str = val_str.replace(',', '.')
    try:
        return float(val_str)
    except ValueError:
        return default


@router.get("")
@router.get("/")
async def get_dashboard_panel():
    """Retorna a visão consolidada de métricas executivas, DRE, DCF, Unit Economics e Mídias."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Carrega todos os parâmetros executivos do banco
        cursor.execute("SELECT metric_key, metric_value, metric_label, metric_group, unit, notes FROM executive_panel_metrics")
        metrics_rows = cursor.fetchall()
        metrics_dict: Dict[str, float] = {}
        metrics_info: Dict[str, dict] = {}

        for row in metrics_rows:
            d = dict(row)
            k = d["metric_key"]
            val = float(d["metric_value"])
            metrics_dict[k] = val
            metrics_info[k] = d

        # Valores padrão com fallback
        capex_maint = metrics_dict.get("capex_maintenance", 15400.0)
        tax_rec = metrics_dict.get("tax_recurring", 18500.0)
        working_cap = metrics_dict.get("working_capital", 125000.0)
        working_cap_growth_pct = metrics_dict.get("working_capital_growth", 12.5)
        bad_debt = metrics_dict.get("bad_debt_provision", 4200.0)
        client_conc = metrics_dict.get("client_concentration", 18.5)
        partner_out_exp = metrics_dict.get("partner_out_expense", 3500.0)
        dcf_val = metrics_dict.get("dcf_valuation", 4500000.0)
        future_pv = metrics_dict.get("future_cash_pv", 3850000.0)
        ebitda_adj_ded = metrics_dict.get("ebitda_adjusted_deductions", 8500.0)
        partner_divs = metrics_dict.get("partner_dividends", 35000.0)
        dso = metrics_dict.get("dso_days", 38.0)
        churn = metrics_dict.get("churn_rate", 2.1)
        arpu = metrics_dict.get("arpu_user_margin", 420.0)
        prod_score = metrics_dict.get("productivity_score", 94.5)
        yoy = metrics_dict.get("yoy_growth", 48.2)
        cpa_camp = metrics_dict.get("cpa_campaign", 45.5)
        cpa_inf = metrics_dict.get("cpa_influencer", 68.0)

        # 2. Carrega despesas financeiras agregadas por categoria
        cursor.execute("SELECT category, amount FROM financial_expenses")
        expenses_rows = cursor.fetchall()
        cost_op_expenses = 0.0
        cost_mkt_expenses = 0.0

        for erow in expenses_rows:
            ed = dict(erow)
            amt = float(ed.get("amount", 0.0))
            cat = ed.get("category", "")
            if cat in ["Marketing", "Marketing & Vendas"]:
                cost_mkt_expenses += amt
            else:
                cost_op_expenses += amt

        # 3. Calcula consumo de tokens AI
        cost_tokens_usd = 0.0
        try:
            cursor.execute("SELECT SUM(cost_usd) FROM brain_chat_messages")
            row_token = cursor.fetchone()
            if row_token and row_token[0]:
                cost_tokens_usd = float(row_token[0])
        except Exception:
            pass

        cost_tokens_brl = cost_tokens_usd * 5.50

        # Base de faturamento estimada (soma de receitas de mídia ou base executiva)
        cursor.execute("SELECT SUM(revenue_generated) FROM media_performance_metrics")
        media_rev_row = cursor.fetchone()
        faturamento_midia = float(media_rev_row[0]) if (media_rev_row and media_rev_row[0]) else 0.0

        faturamento_total = max(faturamento_midia, 325000.0)
        custo_op_total = cost_op_expenses + 42000.0  # custo fixo base + despesas cadastradas
        custo_mkt_total = cost_mkt_expenses + 35000.0

        ebitda = faturamento_total - custo_op_total - custo_mkt_total - cost_tokens_brl
        ebitda_pct = (ebitda / faturamento_total * 100.0) if faturamento_total > 0 else 0.0

        ebitda_ajustado = ebitda - ebitda_adj_ded

        # EBITDA vira caixa de verdade %
        ebitda_cash_conversion_pct = round(((ebitda_ajustado - capex_maint) / ebitda * 100.0), 1) if ebitda > 0 else 85.0

        lucro_liquido = ebitda_ajustado - tax_rec - capex_maint
        fluxo_caixa_livre = ebitda_ajustado - capex_maint - tax_rec - (working_cap * (working_cap_growth_pct / 100.0))

        # LTV Estimado = ARPU / (Churn % / 100)
        ltv = round(arpu / (churn / 100.0), 2) if churn > 0 else 20000.0
        mrr = round(faturamento_total * 0.85, 2)

        # 4. Carrega formatos de mídia
        cursor.execute("SELECT * FROM media_performance_metrics ORDER BY revenue_generated DESC")
        media_rows = cursor.fetchall()
        media_list = [dict(mr) for mr in media_rows]

        return {
            "metrics": {
                # Saúde Financeira & DRE
                "faturamento": round(faturamento_total, 2),
                "ebitda": round(ebitda, 2),
                "ebitda_pct": round(ebitda_pct, 1),
                "ebitda_ajustado": round(ebitda_ajustado, 2),
                "ebitda_cash_conversion_pct": ebitda_cash_conversion_pct,
                "lucro_liquido": round(lucro_liquido, 2),
                "parte_socios": round(partner_divs, 2),
                "custos_operacionais": round(custo_op_total, 2),
                "custos_marketing": round(custo_mkt_total, 2),
                "custos_tokens_ai": round(cost_tokens_brl, 2),

                # Fluxo de Caixa, Valuation & DCF
                "fluxo_caixa_livre": round(fluxo_caixa_livre, 2),
                "dcf_valuation": round(dcf_val, 2),
                "future_cash_pv": round(future_pv, 2),
                "capex_manutencao": round(capex_maint, 2),
                "imposto_recorrente": round(tax_rec, 2),
                "capital_giro": round(working_cap, 2),
                "capital_giro_crescimento_pct": round(working_cap_growth_pct, 1),
                "dso_dias": round(dso, 0),

                # Riscos & Governança
                "inadimplencia_bad_debt": round(bad_debt, 2),
                "cliente_concentrado_pct": round(client_conc, 1),
                "despesa_socio_fora": round(partner_out_exp, 2),

                # Unit Economics & Recorrência
                "ltv": ltv,
                "churn_rate": churn,
                "recorrencia_mrr": mrr,
                "margem_por_usuario_arpu": arpu,
                "produtividade_score": prod_score,
                "crescimento_yoy_pct": yoy,

                # Marketing & CPAs
                "cpa_campanha": cpa_camp,
                "cpa_influencer": cpa_inf,
            },
            "parameters_raw": metrics_dict,
            "media_performance": media_list
        }


@router.post("/metrics")
@router.post("/metrics/")
async def update_executive_metric(
    metric_key: str = Form(...),
    metric_value: str = Form(...),
    notes: Optional[str] = Form("")
):
    """Atualiza o valor de uma métrica executiva no banco de dados."""
    val = parse_float(metric_value)
    now = datetime.now().isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT metric_key FROM executive_panel_metrics WHERE metric_key = ?", (metric_key,))
        if cursor.fetchone():
            cursor.execute(
                "UPDATE executive_panel_metrics SET metric_value = ?, notes = ?, updated_at = ? WHERE metric_key = ?",
                (val, notes.strip() if notes else "", now, metric_key)
            )
        else:
            cursor.execute(
                "INSERT INTO executive_panel_metrics (metric_key, metric_group, metric_label, metric_value, unit, notes, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (metric_key, 'custom', metric_key, val, 'BRL', notes.strip() if notes else "", now)
            )
        conn.commit()
        return {"message": "Métrica atualizada com sucesso.", "metric_key": metric_key, "value": val}


@router.post("/media-performance")
@router.post("/media-performance/")
async def add_or_update_media_performance(
    format_name: str = Form(...),
    clicks: int = Form(0),
    conversions: int = Form(0),
    cpa: str = Form("0.0"),
    revenue_generated: str = Form("0.0"),
    notes: Optional[str] = Form("")
):
    """Cadastra ou atualiza o desempenho de um modelo de mídia/vídeo."""
    cpa_val = parse_float(cpa)
    rev_val = parse_float(revenue_generated)
    now = datetime.now().isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM media_performance_metrics WHERE format_name = ?", (format_name.strip(),))
        row = cursor.fetchone()

        if row:
            cursor.execute(
                """
                UPDATE media_performance_metrics
                SET clicks = ?, conversions = ?, cpa = ?, revenue_generated = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (clicks, conversions, cpa_val, rev_val, notes.strip() if notes else "", now, row[0])
            )
        else:
            cursor.execute(
                """
                INSERT INTO media_performance_metrics (format_name, clicks, conversions, cpa, revenue_generated, notes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (format_name.strip(), clicks, conversions, cpa_val, rev_val, notes.strip() if notes else "", now)
            )
        conn.commit()
        return {"message": "Modelo de mídia salvo com sucesso."}


@router.delete("/media-performance/{id}")
async def delete_media_performance(id: int):
    """Remove um modelo de mídia da tabela de performance."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM media_performance_metrics WHERE id = ?", (id,))
        conn.commit()
        return {"message": "Modelo de mídia removido."}
