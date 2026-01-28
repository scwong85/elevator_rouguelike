import json
import os
import random
import sqlite3
from flask import (
    Flask,
    g,
    render_template,
    session,
    request,
    jsonify,
    redirect,
    url_for,
)

DATABASE = os.path.join(os.path.dirname(__file__), "elevator.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exc):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        with open(os.path.join(os.path.dirname(__file__), "schema.sql"), "r") as f:
            db.executescript(f.read())
        db.commit()


def load_scenarios():
    data_path = os.path.join(os.path.dirname(__file__), "data", "scenarios.json")
    with open(data_path, "r", encoding="utf-8") as f:
        scenarios = json.load(f)
    return scenarios


SCENARIOS = load_scenarios()
SCENARIO_IDS = [s["id"] for s in SCENARIOS]


def pick_run_scenarios():
    count = random.choice([5, 6])
    return random.sample(SCENARIO_IDS, count)


def calculate_alignment(total_charisma, total_karma, total_weird):
    # simple quadrant-ish evaluation
    if total_karma >= 6 and total_charisma >= 6:
        return "Chaotic Good Elevator Therapist"
    if total_karma >= 6 and total_charisma < 6:
        return "Soft‑spoken Moral Backbone"
    if total_karma < 0 and total_weird > 5:
        return "Corporate Villain in a Velvet Suit"
    if total_weird >= 6 and total_charisma >= 4:
        return "Anxious Bystander with Main‑Character Energy"
    if total_weird >= 6:
        return "Resident Elevator Cryptid"
    if total_karma < 0:
        return "Mildly Concerning Button Masher"
    return "Reasonably Normal Human (Suspicious)"


def get_aggregate_stats(scenario_id):
    db = get_db()
    cur = db.execute(
        "SELECT option_index, count FROM scenario_stats WHERE scenario_id = ?",
        (scenario_id,),
    )
    rows = cur.fetchall()
    if not rows:
        return None
    total = sum(r["count"] for r in rows)
    if total == 0:
        return None
    return {r["option_index"]: (r["count"], r["count"] * 100.0 / total) for r in rows}


def record_choice(scenario_id, option_index):
    db = get_db()
    db.execute(
        """
        INSERT INTO scenario_stats (scenario_id, option_index, count)
        VALUES (?, ?, 1)
        ON CONFLICT(scenario_id, option_index)
        DO UPDATE SET count = count + 1
        """,
        (scenario_id, option_index),
    )
    db.commit()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/start", methods=["POST"])
def start():
    session.clear()
    scenario_ids = pick_run_scenarios()
    session["scenario_ids"] = scenario_ids
    session["current_index"] = 0
    session["scores"] = {"charisma": 0, "karma": 0, "weird": 0}
    session["choices"] = []  # list of dicts: {scenario_id, option_index}
    return redirect(url_for("game"))


@app.route("/game")
def game():
    scenario_ids = session.get("scenario_ids")
    current_index = session.get("current_index", 0)
    if not scenario_ids or current_index >= len(scenario_ids):
        return redirect(url_for("summary"))
    return render_template("game.html")


@app.route("/api/current_scenario")
def api_current_scenario():
    scenario_ids = session.get("scenario_ids")
    current_index = session.get("current_index", 0)
    if not scenario_ids or current_index >= len(scenario_ids):
        return jsonify({"done": True})

    scenario_id = scenario_ids[current_index]
    scenario = next(s for s in SCENARIOS if s["id"] == scenario_id)

    return jsonify(
        {
            "done": False,
            "index": current_index,
            "total": len(scenario_ids),
            "scenario": {
                "id": scenario["id"],
                "title": scenario["title"],
                "description": scenario["description"],
                "image": scenario["image"],
                "options": [
                    {"index": i, "text": opt["text"]}
                    for i, opt in enumerate(scenario["options"])
                ],
            },
        }
    )


@app.route("/api/choose", methods=["POST"])
def api_choose():
    payload = request.get_json()
    scenario_id = payload.get("scenario_id")
    option_index = int(payload.get("option_index"))

    scenario = next(s for s in SCENARIOS if s["id"] == scenario_id)
    option = scenario["options"][option_index]

    # update hidden scores
    scores = session.get("scores", {"charisma": 0, "karma": 0, "weird": 0})
    scores["charisma"] += option.get("charisma", 0)
    scores["karma"] += option.get("karma", 0)
    scores["weird"] += option.get("weird", 0)
    session["scores"] = scores

    # record choice for aggregate stats
    record_choice(scenario_id, option_index)

    # track for run summary
    choices = session.get("choices", [])
    choices.append({"scenario_id": scenario_id, "option_index": option_index})
    session["choices"] = choices

    # move to next scenario
    scenario_ids = session.get("scenario_ids")
    current_index = session.get("current_index", 0) + 1
    session["current_index"] = current_index

    return jsonify(
        {
            "consequence_title": option["consequence_title"],
            "consequence_text": option["consequence_text"],
            "consequence_image": option["consequence_image"],
            "next_done": current_index >= len(scenario_ids),
        }
    )


@app.route("/summary")
def summary():
    scenario_ids = session.get("scenario_ids")
    choices = session.get("choices", [])
    scores = session.get("scores", {"charisma": 0, "karma": 0, "weird": 0})

    if not scenario_ids:
        return redirect(url_for("index"))

    detailed = []
    for choice in choices:
        scenario = next(s for s in SCENARIOS if s["id"] == choice["scenario_id"])
        opt = scenario["options"][choice["option_index"]]
        stats = get_aggregate_stats(scenario["id"])
        percent = None
        if stats and choice["option_index"] in stats:
            _, percent = stats[choice["option_index"]]
        detailed.append(
            {
                "scenario_title": scenario["title"],
                "scenario_description": scenario["description"],
                "option_text": opt["text"],
                "player_percent": percent,
            }
        )

    alignment = calculate_alignment(
        scores["charisma"], scores["karma"], scores["weird"]
    )

    return render_template(
        "summary.html", scores=scores, alignment=alignment, detailed=detailed
    )


if __name__ == "__main__":
    if not os.path.exists(DATABASE):
        init_db()
    app.run(debug=True)
