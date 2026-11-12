import os
import sys

# Ensure repository root is in sys.path regardless of how app.py is invoked
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from flask import Flask, render_template, request, redirect, url_for, flash
import src.services as services

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "eukonkanto-wife-carrying-secret-key-2026")


@app.route("/")
def index():
    """Home / Dashboard view."""
    return render_template("index.html")


# =====================================================================
# READ ROUTES (5 FEATURES)
# =====================================================================

@app.route("/entries")
def approved_entries():
    """
    Feature 1 (Read): Approved entries per edition.
    """
    editions = services.get_all_editions()
    default_year = editions[0]["edition_year"] if editions else 2026
    edition_year = request.args.get("edition_year", default=default_year, type=int)
    category_id = request.args.get("category_id", default=None, type=int)

    categories = services.get_categories_for_edition(edition_year)
    entries = services.query_approved_entries(edition_year, category_id)

    return render_template(
        "entries.html",
        editions=editions,
        categories=categories,
        selected_year=edition_year,
        selected_category=category_id,
        entries=entries,
    )


@app.route("/search")
def search():
    """
    Feature 2 (Read): Participant name search.
    """
    query = request.args.get("q", "").strip()
    results = []
    if query:
        results = services.query_name_search(query)
    return render_template("search.html", query=query, results=results)


@app.route("/categories")
def categories_stats():
    """
    Features 3 & 5 (Read): Entries per category breakdown and average final times.
    """
    editions = services.get_all_editions()
    edition_year = request.args.get("edition_year", default=None, type=int)

    breakdown = services.query_entries_per_category(edition_year)
    averages = services.query_average_final_times(edition_year)

    return render_template(
        "categories.html",
        editions=editions,
        selected_year=edition_year,
        breakdown=breakdown,
        averages=averages,
    )


@app.route("/results")
def heat_results():
    """
    Feature 4 (Read): Heat result sheet with time differences.
    """
    heats = services.get_all_heats()
    if not heats:
        return render_template("results.html", heats=[], results=[], selected_key="")

    # Parse heat selection from query param or use first available heat
    default_key = f"{heats[0]['edition_year']}-{heats[0]['race_no']}-{heats[0]['heat_no']}"
    heat_key = request.args.get("heat_key", default=default_key)

    try:
        parts = heat_key.split("-")
        edition_year, race_no, heat_no = int(parts[0]), int(parts[1]), int(parts[2])
    except (ValueError, IndexError):
        edition_year, race_no, heat_no = heats[0]["edition_year"], heats[0]["race_no"], heats[0]["heat_no"]
        heat_key = default_key

    results = services.query_heat_result_sheet(edition_year, race_no, heat_no)
    return render_template(
        "results.html",
        heats=heats,
        selected_key=heat_key,
        results=results,
    )


# =====================================================================
# WRITE ROUTES (3 FEATURES)
# =====================================================================

@app.route("/register", methods=["GET", "POST"])
def register_pair():
    """
    Feature 6 (Write 1 - Create): Register a pair entry.
    """
    if request.method == "POST":
        try:
            edition_year = int(request.form.get("edition_year"))
            category_id = int(request.form.get("category_id"))
            carrier_id = int(request.form.get("carrier_id"))
            carried_id = int(request.form.get("carried_id"))
            bib_number = request.form.get("bib_number")
            bib_number = int(bib_number) if bib_number and bib_number.strip() else None
            status = request.form.get("registration_status", "Pending")

            entry_id = services.write_register_pair(
                edition_year=edition_year,
                category_id=category_id,
                carrier_id=carrier_id,
                carried_id=carried_id,
                bib_number=bib_number,
                registration_status=status,
            )
            flash(f"Successfully registered pair! New Entry ID: #{entry_id} (Status: {status}).", "success")
            if status == "Pending":
                return redirect(url_for("manage_entries"))
            return redirect(url_for("approved_entries", edition_year=edition_year))
        except Exception as e:
            flash(f"Registration Error: {str(e)}", "danger")

    editions = services.get_all_editions()
    categories = services.get_categories_for_edition()
    participants = services.get_all_participants()
    return render_template(
        "register_pair.html",
        editions=editions,
        categories=categories,
        participants=participants,
    )


@app.route("/participants/update-country", methods=["GET", "POST"])
def edit_participant():
    """
    Feature 7 (Write 2 - Update): Change a participant's country.
    """
    if request.method == "POST":
        try:
            participant_id = int(request.form.get("participant_id"))
            new_country_code = request.form.get("country_code", "").strip()

            country_name = services.write_update_participant_country(participant_id, new_country_code)
            flash(f"Participant #{participant_id} country successfully updated to {country_name} ({new_country_code}).", "success")
            return redirect(url_for("edit_participant"))
        except Exception as e:
            flash(f"Update Error: {str(e)}", "danger")

    participants = services.get_all_participants()
    countries = services.get_all_countries()
    return render_template(
        "edit_participant.html",
        participants=participants,
        countries=countries,
    )


@app.route("/entries/manage")
def manage_entries():
    """
    Feature 8 (Write 3 - Delete): View and manage pending entries.
    """
    pending_entries = services.get_all_entries(status_filter="Pending")
    return render_template("manage_entries.html", pending_entries=pending_entries)


@app.route("/entries/delete/<int:entry_id>", methods=["POST"])
def delete_entry(entry_id):
    """
    Feature 8 (Write 3 - Delete Action): Delete a pending entry.
    """
    try:
        services.write_delete_pending_entry(entry_id)
        flash(f"Pending entry #{entry_id} was successfully deleted.", "success")
    except Exception as e:
        flash(f"Delete Error: {str(e)}", "danger")
    return redirect(url_for("manage_entries"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
