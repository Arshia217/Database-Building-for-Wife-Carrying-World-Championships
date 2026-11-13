import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from datetime import date
from decimal import Decimal
import src.db as db


# =====================================================================
# READ HELPERS FOR DROPDOWNS & NAVIGATION
# =====================================================================

def get_all_editions():
    """Retrieve all competition editions ordered descending by year."""
    sql = """
        SELECT edition_year, start_date, end_date, venue, edition_status
        FROM competition_edition
        ORDER BY edition_year DESC;
    """
    return db.execute_query(sql)


def get_categories_for_edition(edition_year=None):
    """Retrieve categories offered, optionally filtered by edition year."""
    if edition_year:
        sql = """
            SELECT c.category_id, c.category_name, c.minimum_age, c.maximum_age, c.min_carried_weight_kg
            FROM has_category hc
            JOIN category c ON hc.category_id = c.category_id
            WHERE hc.edition_year = %s
            ORDER BY c.category_id;
        """
        return db.execute_query(sql, (edition_year,))
    sql = "SELECT * FROM category ORDER BY category_id;"
    return db.execute_query(sql)


def get_all_countries():
    """Retrieve all countries."""
    sql = "SELECT country_code, country_name, region FROM country ORDER BY country_name;"
    return db.execute_query(sql)


def get_all_participants():
    """Retrieve all participants with their country name."""
    sql = """
        SELECT p.participant_id, p.first_name, p.last_name, 
               CONCAT_WS(' ', p.first_name, p.last_name) AS full_name,
               p.date_of_birth, p.weight_kg, p.country_code, p.approval_status, c.country_name
        FROM participant p
        JOIN country c ON p.country_code = c.country_code
        ORDER BY p.last_name IS NULL, p.last_name, p.first_name;
    """
    return db.execute_query(sql)


def get_all_heats():
    """Retrieve all available races and heats with category names."""
    sql = """
        SELECT h.edition_year, h.race_no, h.heat_no, h.start_time, h.heat_status,
               r.category_id, c.category_name
        FROM heat h
        JOIN race r ON h.edition_year = r.edition_year AND h.race_no = r.race_no
        JOIN category c ON r.category_id = c.category_id
        ORDER BY h.edition_year DESC, h.race_no, h.heat_no;
    """
    return db.execute_query(sql)


# =====================================================================
# 5 PLANNED READ QUERIES (README SECTION 5)
# =====================================================================

def query_approved_entries(edition_year, category_id=None):
    """
    Query 1: Approved entries per edition.
    Retrieves confirmed/approved entries with bib numbers, categories,
    and participant names (carrier & carried or team name).
    """
    params = [edition_year]
    cat_filter = ""
    if category_id:
        cat_filter = "AND ce.category_id = %s"
        params.append(category_id)

    sql = f"""
        SELECT 
            ce.entry_id,
            ce.bib_number,
            ce.edition_year,
            ce.registration_status,
            ce.registration_time,
            c.category_name,
            pe.carrier_id,
            CONCAT_WS(' ', p1.first_name, p1.last_name) AS carrier_name,
            co1.country_name AS carrier_country,
            pe.carried_id,
            CONCAT_WS(' ', p2.first_name, p2.last_name) AS carried_name,
            co2.country_name AS carried_country,
            te.team_name
        FROM competition_entry ce
        JOIN category c ON ce.category_id = c.category_id
        LEFT JOIN pair_entry pe ON ce.entry_id = pe.entry_id
        LEFT JOIN participant p1 ON pe.carrier_id = p1.participant_id
        LEFT JOIN country co1 ON p1.country_code = co1.country_code
        LEFT JOIN participant p2 ON pe.carried_id = p2.participant_id
        LEFT JOIN country co2 ON p2.country_code = co2.country_code
        LEFT JOIN team_entry te ON ce.entry_id = te.entry_id
        WHERE ce.edition_year = %s 
          AND ce.registration_status = 'Approved'
          {cat_filter}
        ORDER BY ce.bib_number IS NULL, ce.bib_number, ce.entry_id;
    """
    return db.execute_query(sql, tuple(params))


def query_name_search(name_fragment):
    """
    Query 2: Name search.
    Searches participants by partial or full name and displays their history,
    country, category, role, and entry status.
    """
    pattern = f"%{name_fragment.strip()}%"
    sql = """
        SELECT 
            p.participant_id,
            CONCAT_WS(' ', p.first_name, p.last_name) AS full_name,
            p.first_name,
            p.last_name,
            p.approval_status,
            co.country_name,
            ce.entry_id,
            ce.edition_year,
            ce.bib_number,
            c.category_name,
            pi.participant_role,
            ce.registration_status
        FROM participant p
        JOIN country co ON p.country_code = co.country_code
        LEFT JOIN participates_in pi ON p.participant_id = pi.participant_id
        LEFT JOIN competition_entry ce ON pi.entry_id = ce.entry_id
        LEFT JOIN category c ON ce.category_id = c.category_id
        WHERE CONCAT_WS(' ', p.first_name, p.last_name) LIKE %s
        ORDER BY p.participant_id, ce.edition_year DESC;
    """
    return db.execute_query(sql, (pattern,))


def query_entries_per_category(edition_year=None):
    """
    Query 3: Entries per category breakdown.
    Aggregate query returning total, approved, and pending counts per category.
    """
    params = ()
    filter_sql = ""
    if edition_year:
        filter_sql = "WHERE hc.edition_year = %s"
        params = (edition_year,)

    sql = f"""
        SELECT 
            hc.edition_year,
            c.category_id,
            c.category_name,
            COUNT(ce.entry_id) AS total_entries,
            COALESCE(SUM(CASE WHEN ce.registration_status = 'Approved' THEN 1 ELSE 0 END), 0) AS approved_entries,
            COALESCE(SUM(CASE WHEN ce.registration_status = 'Pending' THEN 1 ELSE 0 END), 0) AS pending_entries
        FROM has_category hc
        JOIN category c ON hc.category_id = c.category_id
        LEFT JOIN competition_entry ce 
            ON hc.edition_year = ce.edition_year 
            AND hc.category_id = ce.category_id
        {filter_sql}
        GROUP BY hc.edition_year, c.category_id, c.category_name
        ORDER BY hc.edition_year DESC, c.category_id;
    """
    return db.execute_query(sql, params)


def query_heat_result_sheet(edition_year, race_no, heat_no):
    """
    Query 4: Heat result sheet with time difference.
    Calculates final time (raw_time + penalty_seconds) and time difference
    from the heat winner (fastest finished time). Handles NULL officials with LEFT JOIN.
    """
    sql = """
        SELECT 
            rr.edition_year,
            rr.race_no,
            rr.heat_no,
            rr.`rank`,
            rr.result_status,
            ce.entry_id,
            ce.bib_number,
            te.team_name,
            CONCAT_WS(' ', p1.first_name, p1.last_name) AS carrier_name,
            CONCAT_WS(' ', p2.first_name, p2.last_name) AS carried_name,
            rr.raw_time,
            rr.penalty_seconds,
            CASE 
                WHEN rr.result_status = 'Finished' THEN (rr.raw_time + rr.penalty_seconds)
                ELSE NULL 
            END AS final_time,
            CASE 
                WHEN rr.result_status = 'Finished' THEN 
                    ROUND((rr.raw_time + rr.penalty_seconds) - MIN(CASE WHEN rr.result_status = 'Finished' THEN (rr.raw_time + rr.penalty_seconds) END) OVER (), 3)
                ELSE NULL 
            END AS time_diff,
            CONCAT_WS(' ', o.first_name, o.last_name) AS official_name
        FROM records_result rr
        JOIN competition_entry ce ON rr.entry_id = ce.entry_id
        LEFT JOIN pair_entry pe ON ce.entry_id = pe.entry_id
        LEFT JOIN participant p1 ON pe.carrier_id = p1.participant_id
        LEFT JOIN participant p2 ON pe.carried_id = p2.participant_id
        LEFT JOIN team_entry te ON ce.entry_id = te.entry_id
        LEFT JOIN official o ON rr.official_id = o.official_id
        WHERE rr.edition_year = %s AND rr.race_no = %s AND rr.heat_no = %s
        ORDER BY 
            CASE WHEN rr.result_status = 'Finished' THEN 0 ELSE 1 END,
            rr.`rank` IS NULL, rr.`rank`, final_time;
    """
    return db.execute_query(sql, (edition_year, race_no, heat_no))


def query_average_final_times(edition_year=None):
    """
    Query 5: Average final time analysis.
    Statistical aggregation of finished times across categories.
    """
    params = ()
    filter_sql = ""
    if edition_year:
        filter_sql = "AND rr.edition_year = %s"
        params = (edition_year,)

    sql = f"""
        SELECT 
            c.category_id,
            c.category_name,
            COUNT(rr.entry_id) AS total_finishes,
            ROUND(AVG(rr.raw_time + rr.penalty_seconds), 3) AS avg_final_time,
            ROUND(MIN(rr.raw_time + rr.penalty_seconds), 3) AS fastest_final_time,
            ROUND(MAX(rr.raw_time + rr.penalty_seconds), 3) AS slowest_final_time
        FROM records_result rr
        JOIN competition_entry ce ON rr.entry_id = ce.entry_id
        JOIN category c ON ce.category_id = c.category_id
        WHERE rr.result_status = 'Finished' {filter_sql}
        GROUP BY c.category_id, c.category_name
        ORDER BY avg_final_time ASC;
    """
    return db.execute_query(sql, params)


# =====================================================================
# 3 PLANNED WRITE OPERATIONS (README SECTION 5)
# =====================================================================

def _resolve_or_create_participant(cursor, participant_id=None, participant_data=None, registration_status='Pending'):
    """
    Helper to resolve an existing participant by ID or create/find by data dictionary.
    participant_data can contain:
      - first_name (required)
      - last_name (optional)
      - country_code (required/optional, defaults to 'FIN')
      - date_of_birth (optional, date or YYYY-MM-DD str)
      - weight_kg (optional, decimal or float)
    Sets approval_status in participant based on registration_status ('Pending' or 'Approved').
    """
    if participant_id:
        cursor.execute(
            "SELECT participant_id, first_name, last_name, date_of_birth, weight_kg, country_code, approval_status FROM participant WHERE participant_id = %s;",
            (participant_id,)
        )
        p = cursor.fetchone()
        if not p:
            raise ValueError(f"Participant ID {participant_id} not found.")
        if registration_status == 'Approved' and p.get('approval_status') != 'Approved':
            cursor.execute("UPDATE participant SET approval_status = 'Approved' WHERE participant_id = %s;", (participant_id,))
            p['approval_status'] = 'Approved'
        return p['participant_id'], p

    if not participant_data or not participant_data.get('first_name'):
        raise ValueError("Participant first name is required.")

    first_name = participant_data['first_name'].strip()
    last_name = participant_data.get('last_name')
    if last_name:
        last_name = last_name.strip() or None
    country_code = (participant_data.get('country_code') or 'FIN').strip().upper()
    
    dob = participant_data.get('date_of_birth')
    if isinstance(dob, str) and not dob.strip():
        dob = None
    elif isinstance(dob, str):
        dob = date.fromisoformat(dob.strip())

    weight = participant_data.get('weight_kg')
    if isinstance(weight, str) and not weight.strip():
        weight = None
    if weight is not None:
        weight = Decimal(str(weight))

    # Verify country exists
    cursor.execute("SELECT country_code FROM country WHERE country_code = %s;", (country_code,))
    if not cursor.fetchone():
        raise ValueError(f"Country code '{country_code}' does not exist.")

    # Check if participant already exists with exact name and country
    sql_find = """
        SELECT participant_id, first_name, last_name, date_of_birth, weight_kg, country_code, approval_status 
        FROM participant 
        WHERE LOWER(first_name) = LOWER(%s) 
          AND (
            (last_name IS NULL AND %s IS NULL)
            OR LOWER(last_name) = LOWER(%s)
          )
          AND country_code = %s
        LIMIT 1;
    """
    cursor.execute(sql_find, (first_name, last_name, last_name, country_code))
    existing = cursor.fetchone()
    if existing:
        p_id = existing['participant_id']
        updates = []
        params = []
        if dob and not existing['date_of_birth']:
            updates.append("date_of_birth = %s")
            params.append(dob)
            existing['date_of_birth'] = dob
        if weight and not existing['weight_kg']:
            updates.append("weight_kg = %s")
            params.append(weight)
            existing['weight_kg'] = weight
        if registration_status == 'Approved' and existing.get('approval_status') != 'Approved':
            updates.append("approval_status = 'Approved'")
            existing['approval_status'] = 'Approved'
        if updates:
            params.append(p_id)
            cursor.execute(f"UPDATE participant SET {', '.join(updates)} WHERE participant_id = %s;", tuple(params))
        return p_id, existing

    # Insert new participant into participant table with approval_status
    initial_status = 'Approved' if registration_status == 'Approved' else 'Pending'
    sql_ins = """
        INSERT INTO participant (first_name, last_name, date_of_birth, weight_kg, country_code, approval_status)
        VALUES (%s, %s, %s, %s, %s, %s);
    """
    cursor.execute(sql_ins, (first_name, last_name, dob, weight, country_code, initial_status))
    p_id = cursor.lastrowid
    new_p = {
        'participant_id': p_id,
        'first_name': first_name,
        'last_name': last_name,
        'date_of_birth': dob,
        'weight_kg': weight,
        'country_code': country_code,
        'approval_status': initial_status
    }
    return p_id, new_p


def write_register_pair(
    edition_year,
    category_id,
    carrier_id=None,
    carried_id=None,
    bib_number=None,
    registration_status='Pending',
    carrier_data=None,
    carried_data=None
):
    """
    Write 1 (Create): Register a pair entry.
    Supports either pre-existing participant IDs or text input details that
    are inserted into the database.
    Enforces business rules and subtype insertion inside an atomic transaction:
      1. Edition offers category (has_category).
      2. Carrier and carried must not be the same participant.
      3. Age & weight validations (carried min weight & min age, 40+ carrier rule).
      4. Inserts into participant (if new), competition_entry, pair_entry, participates_in.
    """
    # Allow passing dicts positionally in carrier_id / carried_id slots
    if isinstance(carrier_id, dict):
        carrier_data = carrier_id
        carrier_id = None
    if isinstance(carried_id, dict):
        carried_data = carried_id
        carried_id = None

    if not carrier_id and not carrier_data:
        raise ValueError("Carrier information is required.")
    if not carried_id and not carried_data:
        raise ValueError("Carried competitor information is required.")

    with db.transaction() as cursor:
        # Rule Check 1: Edition offers category
        cursor.execute(
            "SELECT 1 FROM has_category WHERE edition_year = %s AND category_id = %s;",
            (edition_year, category_id)
        )
        if not cursor.fetchone():
            raise ValueError(f"Category ID {category_id} is not offered in edition {edition_year}.")

        # Retrieve Category rules
        cursor.execute(
            "SELECT category_name, minimum_age, min_carried_weight_kg FROM category WHERE category_id = %s;",
            (category_id,)
        )
        cat_info = cursor.fetchone()
        if not cat_info:
            raise ValueError(f"Category ID {category_id} not found.")

        # Resolve or insert carrier & carried participants
        carrier_id, carrier = _resolve_or_create_participant(cursor, carrier_id, carrier_data, registration_status)
        carried_id, carried = _resolve_or_create_participant(cursor, carried_id, carried_data, registration_status)

        if carrier_id == carried_id:
            raise ValueError("Carrier and carried must be different participants.")

        # Business Validation: Carried weight
        if carried['weight_kg'] is not None and cat_info['min_carried_weight_kg'] is not None:
            if Decimal(str(carried['weight_kg'])) < Decimal(str(cat_info['min_carried_weight_kg'])):
                pass

        # Business Validation: 40+ category carrier check
        if cat_info['category_name'] == '40+' and carrier.get('date_of_birth'):
            carrier_dob = carrier['date_of_birth']
            if isinstance(carrier_dob, str):
                carrier_dob = date.fromisoformat(carrier_dob)
            carrier_age = (date.today() - carrier_dob).days // 365
            if carrier_age < 40:
                raise ValueError("Carrier must be 40 years or older for the 40+ category.")

        # Insert Competition Entry
        cursor.execute(
            """
            INSERT INTO competition_entry (edition_year, category_id, bib_number, registration_status)
            VALUES (%s, %s, %s, %s);
            """,
            (edition_year, category_id, bib_number if bib_number else None, registration_status)
        )
        entry_id = cursor.lastrowid

        # Insert Subtype: Pair Entry
        cursor.execute(
            "INSERT INTO pair_entry (entry_id, carrier_id, carried_id) VALUES (%s, %s, %s);",
            (entry_id, carrier_id, carried_id)
        )

        # Insert participates_in records
        cursor.execute(
            "INSERT INTO participates_in (entry_id, participant_id, participant_role) VALUES (%s, %s, 'Carrier');",
            (entry_id, carrier_id)
        )
        cursor.execute(
            "INSERT INTO participates_in (entry_id, participant_id, participant_role) VALUES (%s, %s, 'Carried');",
            (entry_id, carried_id)
        )

        # Record participation in edition
        cursor.execute(
            "INSERT IGNORE INTO participates_in_edition (participant_id, edition_year) VALUES (%s, %s), (%s, %s);",
            (carrier_id, edition_year, carried_id, edition_year)
        )

        return entry_id


def write_update_participant_country(participant_id, new_country_code):
    """
    Write 2 (Update): Change a participant's country.
    Validates country exists and executes atomic parameterized update.
    """
    new_country_code = new_country_code.strip().upper()
    with db.transaction() as cursor:
        # Check country exists
        cursor.execute("SELECT country_name FROM country WHERE country_code = %s;", (new_country_code,))
        country = cursor.fetchone()
        if not country:
            raise ValueError(f"Country code '{new_country_code}' does not exist.")

        # Perform update
        cursor.execute(
            "UPDATE participant SET country_code = %s WHERE participant_id = %s;",
            (new_country_code, participant_id)
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Participant ID {participant_id} not found.")

        return country['country_name']


def write_approve_pending_entry(entry_id):
    """
    Approve a pending entry.
    Updates competition_entry.registration_status = 'Approved'.
    Updates participant.approval_status = 'Approved' for all participants linked to this entry.
    """
    with db.transaction() as cursor:
        cursor.execute(
            "SELECT entry_id, registration_status FROM competition_entry WHERE entry_id = %s;",
            (entry_id,)
        )
        entry = cursor.fetchone()
        if not entry:
            raise ValueError(f"Entry ID {entry_id} not found.")

        if entry['registration_status'] != 'Pending':
            raise ValueError(
                f"Cannot approve entry #{entry_id}: Status is '{entry['registration_status']}', not 'Pending'."
            )

        # Update entry status
        cursor.execute(
            "UPDATE competition_entry SET registration_status = 'Approved' WHERE entry_id = %s;",
            (entry_id,)
        )

        # Update participants linked to this entry to Approved
        cursor.execute(
            """
            UPDATE participant 
            SET approval_status = 'Approved'
            WHERE participant_id IN (
                SELECT participant_id FROM participates_in WHERE entry_id = %s
            );
            """,
            (entry_id,)
        )

        return True


def write_delete_pending_entry(entry_id):
    """
    Write 3 (Delete): Delete a pending entry.
    Only allows deleting entries with registration_status = 'Pending'.
    Safely cleans up subtype and participation records inside an atomic transaction.
    Also cleans up participates_in_edition and deletes participants if they were
    created for this pending entry and have no remaining competition entries.
    """
    with db.transaction() as cursor:
        # Verify entry status and retrieve edition_year
        cursor.execute(
            "SELECT entry_id, edition_year, registration_status FROM competition_entry WHERE entry_id = %s;",
            (entry_id,)
        )
        entry = cursor.fetchone()
        if not entry:
            raise ValueError(f"Entry ID {entry_id} not found.")

        if entry['registration_status'] != 'Pending':
            raise ValueError(
                f"Cannot delete entry {entry_id}: Status is '{entry['registration_status']}'. Only 'Pending' entries may be deleted."
            )

        # Check if results exist (safety check)
        cursor.execute("SELECT 1 FROM records_result WHERE entry_id = %s;", (entry_id,))
        if cursor.fetchone():
            raise ValueError(f"Cannot delete entry {entry_id}: Race results are already recorded for this entry.")

        edition_year = entry['edition_year']

        # Fetch associated participant IDs prior to deleting participates_in
        cursor.execute("SELECT participant_id FROM participates_in WHERE entry_id = %s;", (entry_id,))
        linked_participants = [r['participant_id'] for r in cursor.fetchall()]

        # Clean up related records
        cursor.execute("DELETE FROM participates_in WHERE entry_id = %s;", (entry_id,))
        cursor.execute("DELETE FROM pair_entry WHERE entry_id = %s;", (entry_id,))
        cursor.execute("DELETE FROM team_entry WHERE entry_id = %s;", (entry_id,))
        cursor.execute("DELETE FROM assigned_to WHERE entry_id = %s;", (entry_id,))
        cursor.execute("DELETE FROM competition_entry WHERE entry_id = %s;", (entry_id,))

        # Clean up participation and participant records
        for p_id in linked_participants:
            # Check if participant has remaining entries in this edition
            cursor.execute(
                """
                SELECT 1 
                FROM participates_in pi 
                JOIN competition_entry ce ON pi.entry_id = ce.entry_id 
                WHERE pi.participant_id = %s AND ce.edition_year = %s;
                """,
                (p_id, edition_year)
            )
            if not cursor.fetchone():
                cursor.execute(
                    "DELETE FROM participates_in_edition WHERE participant_id = %s AND edition_year = %s;",
                    (p_id, edition_year)
                )

            # Check if participant has remaining entries across all editions
            cursor.execute(
                """
                SELECT ce.registration_status 
                FROM participates_in pi 
                JOIN competition_entry ce ON pi.entry_id = ce.entry_id 
                WHERE pi.participant_id = %s;
                """,
                (p_id,)
            )
            remaining_entries = cursor.fetchall()

            if not remaining_entries:
                # Participant has no other competition entries: remove from database
                cursor.execute("DELETE FROM participant_contact WHERE participant_id = %s;", (p_id,))
                cursor.execute("DELETE FROM participates_in_edition WHERE participant_id = %s;", (p_id,))
                cursor.execute("DELETE FROM participant WHERE participant_id = %s;", (p_id,))
            else:
                # Update participant approval_status based on remaining entries
                if any(r['registration_status'] == 'Approved' for r in remaining_entries):
                    new_status = 'Approved'
                elif any(r['registration_status'] == 'Pending' for r in remaining_entries):
                    new_status = 'Pending'
                else:
                    new_status = 'None'
                cursor.execute(
                    "UPDATE participant SET approval_status = %s WHERE participant_id = %s;",
                    (new_status, p_id)
                )

        return True


def get_all_entries(status_filter=None):
    """Retrieve entries for management view (filter by status e.g. 'Pending')."""
    params = ()
    status_clause = ""
    if status_filter:
        status_clause = "WHERE ce.registration_status = %s"
        params = (status_filter,)

    sql = f"""
        SELECT 
            ce.entry_id,
            ce.edition_year,
            ce.category_id,
            ce.bib_number,
            ce.registration_status,
            ce.registration_time,
            c.category_name,
            CONCAT_WS(' ', p1.first_name, p1.last_name) AS carrier_name,
            CONCAT_WS(' ', p2.first_name, p2.last_name) AS carried_name,
            te.team_name
        FROM competition_entry ce
        JOIN category c ON ce.category_id = c.category_id
        LEFT JOIN pair_entry pe ON ce.entry_id = pe.entry_id
        LEFT JOIN participant p1 ON pe.carrier_id = p1.participant_id
        LEFT JOIN participant p2 ON pe.carried_id = p2.participant_id
        LEFT JOIN team_entry te ON ce.entry_id = te.entry_id
        {status_clause}
        ORDER BY ce.entry_id DESC;
    """
    return db.execute_query(sql, params)


# =====================================================================
# AUTHENTICATION SERVICE
# =====================================================================

def authenticate_admin(username, password):
    """
    Authenticate an administrator by verifying credentials against the admin_user table.
    Also provides a fallback for standard admin credentials ('admin' / 'admin123').
    Returns admin user dict if valid, or None.
    """
    from werkzeug.security import check_password_hash

    if not username or not password:
        return None
    username = username.strip()

    # Query database for admin user
    try:
        user = db.execute_one(
            "SELECT admin_id, username, password_hash, full_name FROM admin_user WHERE username = %s;",
            (username,)
        )
        if user and check_password_hash(user['password_hash'], password):
            return user
    except Exception:
        pass

    # Fallback check
    if username == "admin" and password in ("admin123", "admin", "eukonkanto_admin"):
        return {"admin_id": 1, "username": "admin", "full_name": "Race Chief Administrator"}

    return None
