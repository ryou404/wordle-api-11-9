import os
import random
import uuid
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Wordle API Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

WORD_BANK = [
    "APPLE", "TRAIN", "HOUSE", "PLANT", "SMART", "WORLD", "LIGHT", "BRAIN", "CLOUD", "WATER",
    "ABOUT", "ABOVE", "ACTOR", "ACUTE", "ADMIT", "ADOPT", "ADULT", "AFTER", "AGAIN", "AGENT",
    "AGREE", "AHEAD", "ALARM", "ALBUM", "ALERT", "ALIEN", "ALIKE", "ALIVE", "ALLOW", "ALONE",
    "ALONG", "ALTER", "AMONG", "ANGER", "ANGLE", "ANGRY", "APART", "APPLY", "ARGUE", "ARISE",
    "ARRAY", "ARROW", "ASIDE", "ASSET", "AUDIO", "AUDIT", "AVOID", "AWAKE", "AWARE", "BADGE",
    "BAKER", "BASIC", "BASIS", "BEACH", "BEGIN", "BEING", "BELOW", "BENCH", "BLACK", "BLAME",
    "BLANK", "BLAST", "BLEED", "BLEND", "BLOCK", "BLOOD", "BOARD", "BOAST", "BONUS", "BOOST",
    "BOUND", "BREAD", "BREAK", "BRICK", "BRIEF", "BRING", "BROAD", "BROWN", "BRUSH", "BUILD",
    "BUNCH", "BUYER", "CABLE", "CANDY", "CARGO", "CARRY", "CATCH", "CAUSE", "CHAIN", "CHAIR",
    "CHALK", "CHARM", "CHART", "CHASE", "CHEAP", "CHECK", "CHEST", "CHIEF", "CHILD", "CHOSE",
    "CIVIL", "CLAIM", "CLASS", "CLEAN", "CLEAR", "CLIMB", "CLOCK", "CLOSE", "COACH", "COAST",
    "COUNT", "COURT", "COVER", "CRASH", "CREAM", "CRIME", "CROSS", "CROWD", "CROWN", "CURVE",
    "CYCLE", "DAILY", "DANCE", "DEATH", "DELAY", "DEPTH", "DRAFT", "DRAMA", "DREAM", "DRIVE",
    "EAGLE", "EARLY", "EARTH", "EIGHT", "EMPTY", "ENEMY", "ENJOY", "ENTER", "EQUAL", "ERROR",
    "EVENT", "EVERY", "EXACT", "EXIST", "FAITH", "FALSE", "FAULT", "FIELD", "FIGHT", "FINAL",
    "FIRST", "FLAME", "FLASH", "FLOAT", "FLOOR", "FLOUR", "FLUID", "FOCUS", "FORCE", "FORTH",
    "FORTY", "FORUM", "FRAME", "FRESH", "FRONT", "FRUIT", "GIANT", "GLASS", "GLOBE", "GRACE",
    "GRADE", "GRAND", "GRANT", "GRASS", "GREAT", "GREEN", "GROUP", "GUARD", "GUESS", "GUIDE",
    "HAPPY", "HEART", "HEAVY", "HOTEL", "HUMAN", "IMAGE", "INDEX", "INPUT", "ISSUE", "JUDGE",
    "KNIFE", "LAYER", "LEMON", "LEVEL", "LIMIT", "LUNCH", "MAGIC", "MAJOR", "MARCH", "MATCH",
    "MEDAL", "MONEY", "MONTH", "MUSIC", "NIGHT", "NOVEL", "NURSE", "OCEAN", "OFFER", "ORDER"
]

total_games = 0
total_wins = 0
games_db: Dict[str, dict] = {}


class NewGameRequest(BaseModel):
    hard_mode: Optional[bool] = False


class GuessRequest(BaseModel):
    game_id: str
    guess: str


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/stats")
def get_stats():
    win_rate = (total_wins / total_games * 100) if total_games > 0 else 0.0
    return {
        "total_games": total_games,
        "wins": total_wins,
        "win_rate": round(win_rate, 1)
    }


@app.post("/api/new-game")
def start_new_game(req: Optional[NewGameRequest] = None, hard_mode: Optional[bool] = None):
    is_hard = False
    if req is not None and req.hard_mode:
        is_hard = True
    elif hard_mode is not None:
        is_hard = hard_mode

    game_id = str(uuid.uuid4())
    target_word = random.choice(WORD_BANK)
    games_db[game_id] = {
        "target": target_word,
        "status": "PLAYING",
        "attempts": 0,
        "hard_mode": is_hard,
        "revealed_correct": {},
        "counted": False
    }

    win_rate = (total_wins / total_games * 100) if total_games > 0 else 0.0
    return {
        "game_id": game_id,
        "message": "New game started!",
        "hard_mode": is_hard,
        "stats": {
            "total_games": total_games,
            "wins": total_wins,
            "win_rate": round(win_rate, 1)
        }
    }


@app.post("/api/guess")
def process_guess(req: GuessRequest):
    global total_games, total_wins

    game_id = req.game_id
    if game_id not in games_db:
        raise HTTPException(status_code=404, detail="Game session not found.")

    session = games_db[game_id]

    if session["status"] in ["WON", "LOST"]:
        raise HTTPException(status_code=409, detail="Game has already ended.")

    guess = req.guess.upper()

    if len(guess) != 5 or not guess.isascii() or not guess.isalpha():
        raise HTTPException(status_code=400, detail="Guess must be 5 English letters.")

    if guess not in WORD_BANK:
        raise HTTPException(status_code=400, detail="Word not in dictionary")

    if session.get("hard_mode", False):
        revealed = session.get("revealed_correct", {})
        for idx, char in revealed.items():
            if guess[idx] != char:
                raise HTTPException(
                    status_code=400,
                    detail="Hard Mode: Must use revealed hint at green position"
                )

    target = session["target"]
    feedback = ["absent"] * 5
    counts = {}

    for char in target:
        counts[char] = counts.get(char, 0) + 1

    for i in range(5):
        if guess[i] == target[i]:
            feedback[i] = "correct"
            counts[guess[i]] -= 1
            session["revealed_correct"][i] = guess[i]

    for i in range(5):
        if feedback[i] != "correct" and counts.get(guess[i], 0) > 0:
            feedback[i] = "present"
            counts[guess[i]] -= 1

    session["attempts"] += 1
    is_correct = (guess == target)

    target_word_to_return = None
    if is_correct:
        session["status"] = "WON"
        target_word_to_return = target
        if not session["counted"]:
            total_games += 1
            total_wins += 1
            session["counted"] = True
    elif session["attempts"] >= 6:
        session["status"] = "LOST"
        target_word_to_return = target
        if not session["counted"]:
            total_games += 1
            session["counted"] = True
    else:
        target_word_to_return = None

    win_rate = (total_wins / total_games * 100) if total_games > 0 else 0.0

    return {
        "guess": guess,
        "feedback": feedback,
        "is_correct": is_correct,
        "status": session["status"],
        "target_word": target_word_to_return,
        "stats": {
            "total_games": total_games,
            "wins": total_wins,
            "win_rate": round(win_rate, 1)
        }
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)