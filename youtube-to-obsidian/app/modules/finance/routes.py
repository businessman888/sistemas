import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Form, Query

from app.core.database import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/finance", tags=["finance"])


def row_to_dict(row):
    if not row:
        return None
    d = dict(row)
    # Check if pending expense is overdue
    if d.get("status") == "pending" and d.get("due_date"):
        try:
            due = datetime.strptime(d["due_date"], "%Y-%m-%d").date()
            if due < date.today():
                d["status"] = "overdue"
        except ValueError:
            pass
    return d


@router.get("/expenses")
async def list_expenses(
    period_type: Optional[str] = None,
    period_value: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None
):
    """Lista despesas financeiras com suporte a filtros por período e buscas."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM financial_expenses"
        conditions = []
        params = []

        if category and isinstance(category, str) and category != "all":
            conditions.append("category = ?")
            params.append(category)

        if search and isinstance(search, str) and search.strip():
            conditions.append("(title LIKE ? OR notes LIKE ? OR category LIKE ?)")
            search_param = f"%{search.strip()}%"
            params.extend([search_param, search_param, search_param])

        # Filtro de período por data de vencimento (due_date YYYY-MM-DD)
        if period_type and period_value:
            if period_type == "mes": # period_value="2026-07"
                conditions.append("due_date LIKE ?")
                params.append(f"{period_value}%")
            elif period_type == "ano": # period_value="2026"
                conditions.append("due_date LIKE ?")
                params.append(f"{period_value}%")
            elif period_type == "quarter": # period_value="2026-Q3"
                parts = period_value.split("-")
                if len(parts) == 2:
                    yr, q = parts[0], parts[1]
                    q_months = {
                        "Q1": ["01", "02", "03"],
                        "Q2": ["04", "05", "06"],
                        "Q3": ["07", "08", "09"],
                        "Q4": ["10", "11", "12"],
                    }
                    if q in q_months:
                        m_list = [f"'{yr}-{m}'" for m in q_months[q]]
                        q_conds = [f"due_date LIKE '{yr}-{m}%'" for m in q_months[q]]
                        conditions.append(f"({' OR '.join(q_conds)})")
            elif period_type == "semestre": # period_value="2026-S1"
                parts = period_value.split("-")
                if len(parts) == 2:
                    yr, s = parts[0], parts[1]
                    s_months = {
                        "S1": ["01", "02", "03", "04", "05", "06"],
                        "S2": ["07", "08", "09", "10", "11", "12"],
                    }
                    if s in s_months:
                        s_conds = [f"due_date LIKE '{yr}-{m}%'" for m in s_months[s]]
                        conditions.append(f"({' OR '.join(s_conds)})")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY due_date ASC, id DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        items = [row_to_dict(row) for row in rows]

        # Filtragem pós-query por status se especificado
        if status and status != "all":
            if status == "overdue":
                items = [item for item in items if item["status"] == "overdue"]
            else:
                items = [item for item in items if item["status"] == status]

        return items


def parse_amount(val) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if not val:
        return 0.0
    val_str = str(val).replace('R$', '').replace(' ', '').strip()
    if not val_str:
        return 0.0

    # If both ',' and '.' exist:
    if ',' in val_str and '.' in val_str:
        if val_str.rfind(',') > val_str.rfind('.'):
            # Brazilian format: 1.250,50 -> 1250.50
            val_str = val_str.replace('.', '').replace(',', '.')
        else:
            # US format: 1,250.50 -> 1250.50
            val_str = val_str.replace(',', '')
    elif ',' in val_str:
        # Only comma exists, e.g. 114,21 -> 114.21
        val_str = val_str.replace(',', '.')

    try:
        return float(val_str)
    except ValueError:
        return 0.0

def parse_due_date(dt_str: str) -> str:
    dt_str = dt_str.strip()
    # Check if DD/MM/YYYY
    if '/' in dt_str:
        parts = dt_str.split('/')
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    return dt_str

@router.post("/expenses")
@router.post("/expenses/")
async def create_expense(
    title: str = Form(...),
    category: str = Form(...),
    amount: str = Form(...),
    periodicity: str = Form(...),
    due_date: str = Form(...),
    status: str = Form("pending"),
    notes: Optional[str] = Form("")
):
    """Cadastra uma nova despesa financeira."""
    now = datetime.now().isoformat()
    parsed_amt = parse_amount(amount)
    parsed_date = parse_due_date(due_date)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO financial_expenses (title, category, amount, periodicity, due_date, status, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (title.strip(), category.strip(), parsed_amt, periodicity, parsed_date, status, notes.strip() if notes else "", now)
            )
            conn.commit()
            item_id = cursor.lastrowid

            cursor.execute("SELECT * FROM financial_expenses WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            return row_to_dict(row)
        except Exception as e:
            logger.exception("Erro ao cadastrar despesa")
            raise HTTPException(status_code=400, detail=f"Erro ao cadastrar despesa: {e}")


@router.get("/summary")
@router.get("/expenses/summary")
async def get_financial_summary(
    period_type: Optional[str] = Query(None),
    period_value: Optional[str] = Query(None)
):
    """Retorna métricas consolidadas e estatísticas para o Dashboard."""
    expenses = await list_expenses(period_type=period_type, period_value=period_value)

    total_amount = 0.0
    paid_amount = 0.0
    pending_amount = 0.0
    overdue_amount = 0.0

    paid_count = 0
    pending_count = 0
    overdue_count = 0

    category_totals: Dict[str, float] = {}

    for item in expenses:
        amt = float(item.get("amount", 0.0))
        st = item.get("status")
        cat = item.get("category", "Outros")

        total_amount += amt
        category_totals[cat] = category_totals.get(cat, 0.0) + amt

        if st == "paid":
            paid_amount += amt
            paid_count += 1
        elif st == "overdue":
            overdue_amount += amt
            overdue_count += 1
        else: # pending
            pending_amount += amt
            pending_count += 1

    # Formata categorias com percentuais
    categories_list = []
    for cat_name, cat_amt in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
        pct = (cat_amt / total_amount * 100.0) if total_amount > 0 else 0.0
        categories_list.append({
            "category": cat_name,
            "amount": round(cat_amt, 2),
            "percentage": round(pct, 1)
        })

    # Próximos vencimentos (pendentes nos próximos 15 dias ou já vencidos)
    upcoming = [item for item in expenses if item.get("status") in ["pending", "overdue"]]
    upcoming.sort(key=lambda x: x.get("due_date", ""))

    return {
        "total_amount": round(total_amount, 2),
        "paid_amount": round(paid_amount, 2),
        "pending_amount": round(pending_amount, 2),
        "overdue_amount": round(overdue_amount, 2),
        "total_count": len(expenses),
        "paid_count": paid_count,
        "pending_count": pending_count,
        "overdue_count": overdue_count,
        "categories": categories_list,
        "upcoming_due": upcoming[:5]
    }


@router.get("/expenses/{id}")
async def get_expense(id: int):
    """Retorna detalhes de uma despesa específica."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM financial_expenses WHERE id = ?", (id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Despesa não encontrada.")
        return row_to_dict(row)


@router.put("/expenses/{id}")
@router.put("/expenses/{id}/")
async def update_expense(
    id: int,
    title: str = Form(...),
    category: str = Form(...),
    amount: str = Form(...),
    periodicity: str = Form(...),
    due_date: str = Form(...),
    status: str = Form("pending"),
    notes: Optional[str] = Form("")
):
    """Atualiza os dados de uma despesa existente."""
    parsed_amt = parse_amount(amount)
    parsed_date = parse_due_date(due_date)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM financial_expenses WHERE id = ?", (id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Despesa não encontrada.")

        try:
            cursor.execute(
                """
                UPDATE financial_expenses
                SET title = ?, category = ?, amount = ?, periodicity = ?, due_date = ?, status = ?, notes = ?
                WHERE id = ?
                """,
                (title.strip(), category.strip(), parsed_amt, periodicity, parsed_date, status, notes.strip() if notes else "", id)
            )
            conn.commit()

            cursor.execute("SELECT * FROM financial_expenses WHERE id = ?", (id,))
            row = cursor.fetchone()
            return row_to_dict(row)
        except Exception as e:
            logger.exception("Erro ao atualizar despesa")
            raise HTTPException(status_code=400, detail=f"Erro ao atualizar despesa: {e}")


@router.patch("/expenses/{id}/status")
async def toggle_expense_status(id: int, status: str = Form(...)):
    """Atualiza rapidamente o status de uma despesa ('paid' ou 'pending')."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM financial_expenses WHERE id = ?", (id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Despesa não encontrada.")

        try:
            cursor.execute("UPDATE financial_expenses SET status = ? WHERE id = ?", (status, id))
            conn.commit()

            cursor.execute("SELECT * FROM financial_expenses WHERE id = ?", (id,))
            row = cursor.fetchone()
            return row_to_dict(row)
        except Exception as e:
            logger.exception("Erro ao alterar status da despesa")
            raise HTTPException(status_code=400, detail=f"Erro ao alterar status: {e}")


@router.delete("/expenses/{id}")
async def delete_expense(id: int):
    """Remove uma despesa do banco de dados."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM financial_expenses WHERE id = ?", (id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Despesa não encontrada.")

        try:
            cursor.execute("DELETE FROM financial_expenses WHERE id = ?", (id,))
            conn.commit()
            return {"message": "Despesa removida com sucesso."}
        except Exception as e:
            logger.exception("Erro ao excluir despesa")
            raise HTTPException(status_code=400, detail=f"Erro ao excluir despesa: {e}")

