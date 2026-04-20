#!/usr/bin/env python3
import sys
sys.dont_write_bytecode = True
import os
import hashlib
import json
import secrets
from datetime import datetime

# ============================================================================
# CRYPTOGRAPHY IMPORT - System first, bundled fallback for Python 3.13+
# ============================================================================

# Get the directory where this file is located
current_dir = os.path.dirname(os.path.abspath(__file__))
assets_dir = os.path.join(current_dir, 'assets')

HAS_CRYPTO = False
AESGCM = None

# ========== DEBUG CODE (commented out) ==========
# print("\n" + "="*60)
# print("[CRYPTO DEBUG] Starting cryptography import...")
# print("="*60)
# print(f"Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
# print(f"Assets directory: {assets_dir}")
# print(f"Assets exists: {os.path.exists(assets_dir)}")
# input(">>> Press Enter to continue...")
# ========== END DEBUG ==========

# Step 1: Try system installation first (any Python version)
# ========== DEBUG CODE (commented out) ==========
# print("\n[STEP 1] Trying system installation...")
# ========== END DEBUG ==========
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTO = True
    # ========== DEBUG CODE (commented out) ==========
    # print("[STEP 1] ✅ SUCCESS! Using system installation")
    # import cryptography
    # print(f"  Cryptography path: {cryptography.__file__}")
    # ========== END DEBUG ==========
except ImportError as e:
    # ========== DEBUG CODE (commented out) ==========
    # print(f"[STEP 1] ❌ FAILED: {e}")
    # ========== END DEBUG ==========
    pass

# ========== DEBUG CODE (commented out) ==========
# input(">>> Press Enter to continue...")
# ========== END DEBUG ==========

# Step 2: Fallback to bundled (Python 3.13+ only)
if not HAS_CRYPTO:
    # ========== DEBUG CODE (commented out) ==========
    # print(f"\n[STEP 2] Checking fallback conditions...")
    # print(f"  HAS_CRYPTO: {HAS_CRYPTO}")
    # print(f"  Python >= 3.13: {sys.version_info >= (3, 13)}")
    # ========== END DEBUG ==========
    
    if sys.version_info >= (3, 13):
        # ========== DEBUG CODE (commented out) ==========
        # print("[STEP 2] Python 3.13+ detected, attempting bundled fallback...")
        # ========== END DEBUG ==========
        
        # Add bundled paths only if they exist
        cffi_dir = os.path.join(assets_dir, 'cffi')
        crypto_dir = os.path.join(assets_dir, 'cryptography')
        
        # ========== DEBUG CODE (commented out) ==========
        # print(f"  cffi_dir exists: {os.path.exists(cffi_dir)}")
        # print(f"  crypto_dir exists: {os.path.exists(crypto_dir)}")
        # ========== END DEBUG ==========
        
        if os.path.exists(assets_dir) and assets_dir not in sys.path:
            sys.path.insert(0, assets_dir)
            # ========== DEBUG CODE (commented out) ==========
            # print(f"  Added to sys.path: {assets_dir}")
            # ========== END DEBUG ==========
        if os.path.exists(cffi_dir) and cffi_dir not in sys.path:
            sys.path.insert(0, cffi_dir)
            # ========== DEBUG CODE (commented out) ==========
            # print(f"  Added to sys.path: {cffi_dir}")
            # ========== END DEBUG ==========
        if os.path.exists(crypto_dir) and crypto_dir not in sys.path:
            sys.path.insert(0, crypto_dir)
            # ========== DEBUG CODE (commented out) ==========
            # print(f"  Added to sys.path: {crypto_dir}")
            # ========== END DEBUG ==========
        
        # ========== DEBUG CODE (commented out) ==========
        # print("\n  Attempting import from bundled...")
        # ========== END DEBUG ==========
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            HAS_CRYPTO = True
            # ========== DEBUG CODE (commented out) ==========
            # print("[STEP 2] ✅ SUCCESS! Using bundled cryptography")
            # ========== END DEBUG ==========
        except ImportError as e:
            # ========== DEBUG CODE (commented out) ==========
            # print(f"[STEP 2] ❌ FAILED: {e}")
            # ========== END DEBUG ==========
            pass
    # ========== DEBUG CODE (commented out) ==========
    # else:
    #     print("[STEP 2] SKIPPING - Python version < 3.13, no bundled fallback available")
    # ========== END DEBUG ==========
# ========== DEBUG CODE (commented out) ==========
# else:
#     print("\n[STEP 2] SKIPPING - Already using system installation")
# ========== END DEBUG ==========

# ========== DEBUG CODE (commented out) ==========
# input(">>> Press Enter to continue...")
# ========== END DEBUG ==========

# Step 3: Final result
# ========== DEBUG CODE (commented out) ==========
# print("\n" + "="*60)
# print("[CRYPTO DEBUG] FINAL RESULT")
# print("="*60)
# if HAS_CRYPTO:
#     print(f"✅ CRYPTO AVAILABLE")
#     print(f"   AESGCM: {AESGCM}")
# else:
#     print(f"❌ CRYPTO NOT AVAILABLE")
#     print(f"   Install with: pip install cryptography")
# print("="*60 + "\n")
# input(">>> Press Enter to continue...")
# ========== END DEBUG ==========

# Import secure session (will be used by retrieve_for_folder)
from secure_session import SecureSessionStorage


# ============================================================================
# KEY DERIVATION
# ============================================================================

def derive_key(secret, salt):
    """
    Derive a 32-byte key from secret and salt.
    Uses SHA256 (fast, but entropy depends on secret strength).
    For strong secrets (12-word phrases), this is sufficient.
    """
    if isinstance(secret, str):
        secret = secret.encode('utf-8')
    if isinstance(salt, str):
        salt = salt.encode('utf-8')
    
    combined = secret + b':' + salt
    return hashlib.sha256(combined).digest()


def combine_keys(key1, key2):
    """Combine two 32-byte keys into one master key."""
    combined = key1 + key2
    return hashlib.sha256(combined).digest()


# ============================================================================
# BIP-39 WORD LIST (2048 common words)
# ============================================================================

BIP39_WORDS = [
    "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract", 
    "absurd", "abuse", "access", "accident", "account", "accuse", "achieve", "acid",
    "acoustic", "acquire", "across", "act", "action", "actor", "actress", "actual",
    "adapt", "add", "addict", "address", "adjust", "admit", "adult", "advance",
    "advice", "aerobic", "affair", "afford", "afraid", "africa", "after", "again",
    "age", "agent", "agree", "ahead", "aim", "air", "airport", "aisle", "alarm",
    "album", "alcohol", "alert", "alien", "all", "alley", "allow", "almost",
    "alone", "alpha", "already", "also", "alter", "always", "amateur", "amazing",
    "among", "amount", "amused", "analyst", "anchor", "ancient", "anger", "angle",
    "angry", "animal", "ankle", "announce", "annual", "another", "answer", "antenna",
    "antique", "anxiety", "any", "apart", "apology", "appear", "apple", "approve",
    "april", "arch", "arctic", "area", "arena", "argue", "arm", "armed", "armor",
    "army", "around", "arrange", "arrest", "arrive", "arrow", "art", "artefact",
    "artist", "artwork", "ask", "aspect", "assault", "asset", "assist", "assume",
    "asthma", "athlete", "atom", "attack", "attend", "attitude", "attract", "auction",
    "audit", "august", "aunt", "author", "auto", "autumn", "average", "avocado",
    "avoid", "awake", "aware", "away", "awesome", "awful", "awkward", "axis",
    "baby", "bachelor", "bacon", "badge", "bag", "balance", "balcony", "ball",
    "bamboo", "banana", "banner", "bar", "barely", "bargain", "barrel", "base",
    "basic", "basket", "battle", "beach", "bean", "beauty", "because", "become",
    "beef", "before", "begin", "behave", "behind", "believe", "below", "belt",
    "bench", "benefit", "best", "betray", "better", "between", "beyond", "bicycle",
    "bid", "bike", "bind", "biology", "bird", "birth", "bitter", "black", "blade",
    "blame", "blanket", "blast", "bleak", "bless", "blind", "blood", "blossom",
    "blouse", "blue", "blur", "blush", "board", "boat", "body", "boil", "bomb",
    "bone", "bonus", "book", "boost", "border", "boring", "borrow", "boss", "bottom",
    "bounce", "box", "boy", "bracket", "brain", "brand", "brass", "brave", "bread",
    "breeze", "brick", "bridge", "brief", "bright", "bring", "brisk", "broccoli",
    "broken", "bronze", "broom", "brother", "brown", "brush", "bubble", "buddy",
    "budget", "buffalo", "build", "bulb", "bulk", "bullet", "bundle", "bunker",
    "burden", "burger", "burst", "bus", "business", "busy", "butter", "buyer",
    "buzz", "cabbage", "cabin", "cable", "cactus", "cage", "cake", "call", "calm",
    "camera", "camp", "can", "canal", "cancel", "candy", "cannon", "canoe", "canvas",
    "canyon", "capable", "capital", "captain", "car", "carbon", "card", "cargo",
    "carpet", "carry", "cart", "case", "cash", "casino", "castle", "casual",
    "cat", "catalog", "catch", "category", "cattle", "caught", "cause", "caution",
    "cave", "ceiling", "celery", "cement", "census", "century", "cereal", "certain",
    "chair", "chalk", "champion", "change", "chaos", "chapter", "charge", "chase",
    "chat", "cheap", "check", "cheese", "chef", "cherry", "chest", "chicken",
    "chief", "child", "chimney", "choice", "choose", "chronic", "chuckle", "chunk",
    "churn", "cigar", "cinnamon", "circle", "citizen", "city", "civil", "claim",
    "clap", "clarify", "claw", "clay", "clean", "clerk", "clever", "click", "client",
    "cliff", "climb", "clinic", "clip", "clock", "clog", "close", "cloth", "cloud",
    "clown", "club", "clump", "cluster", "clutch", "coach", "coast", "coconut",
    "code", "coffee", "coil", "coin", "collect", "color", "column", "combine",
    "come", "comfort", "comic", "common", "company", "concert", "conduct", "confirm",
    "congress", "connect", "consider", "control", "convince", "cook", "cool",
    "copper", "copy", "coral", "core", "corn", "correct", "cost", "cotton", "couch",
    "country", "couple", "course", "cousin", "cover", "coyote", "crack", "cradle",
    "craft", "cram", "crane", "crash", "crater", "crawl", "crazy", "cream", "credit",
    "creek", "crew", "cricket", "crime", "crisp", "critic", "crop", "cross", "crouch",
    "crowd", "crucial", "cruel", "cruise", "crumble", "crunch", "crush", "cry",
    "crystal", "cube", "culture", "cup", "cupboard", "curious", "current", "curtain",
    "curve", "cushion", "custom", "cute", "cycle", "dad", "damage", "damp", "dance",
    "danger", "daring", "dash", "daughter", "dawn", "day", "deal", "debate", "debris",
    "decade", "december", "decide", "decline", "decorate", "decrease", "deer",
    "defense", "define", "defy", "degree", "delay", "deliver", "demand", "demise",
    "denial", "dentist", "deny", "depart", "depend", "deposit", "depth", "deputy",
    "derive", "describe", "desert", "design", "desk", "despair", "destroy", "detail",
    "detect", "develop", "device", "devote", "diagram", "dial", "diamond", "diary",
    "dice", "diesel", "diet", "differ", "digital", "dignity", "dilemma", "dinner",
    "dinosaur", "direct", "dirt", "disagree", "discover", "disease", "dish", "dismiss",
    "disorder", "display", "distance", "divert", "divide", "divorce", "dizzy", "doctor",
    "document", "dog", "doll", "dolphin", "domain", "donate", "donkey", "donor",
    "door", "dose", "double", "dove", "draft", "dragon", "drama", "drastic", "draw",
    "dream", "dress", "drift", "drill", "drink", "drip", "drive", "drop", "drum",
    "dry", "duck", "dumb", "dune", "during", "dust", "dutch", "duty", "dwarf",
    "dynamic", "eager", "eagle", "early", "earn", "earth", "easily", "east", "easy",
    "echo", "ecology", "economy", "edge", "edit", "educate", "effort", "egg", "eight",
    "either", "elbow", "elder", "electric", "elegant", "element", "elephant", "elevator",
    "elite", "else", "embark", "embody", "embrace", "emerge", "emotion", "employ",
    "empower", "empty", "enable", "enact", "end", "endless", "endorse", "enemy",
    "energy", "enforce", "engage", "engine", "enhance", "enjoy", "enlist", "enough",
    "enrich", "enroll", "ensure", "enter", "entire", "entry", "envelope", "episode",
    "equal", "equip", "era", "erase", "erode", "erosion", "error", "erupt", "escape",
    "essay", "essence", "estate", "eternal", "ethics", "evidence", "evil", "evoke",
    "evolve", "exact", "example", "excess", "exchange", "excite", "exclude", "excuse",
    "execute", "exercise", "exhaust", "exhibit", "exile", "exist", "exit", "exotic",
    "expand", "expect", "expire", "explain", "expose", "express", "extend", "extra",
    "eye", "eyebrow", "fabric", "face", "faculty", "fade", "faint", "faith", "fall",
    "false", "fame", "family", "famous", "fan", "fancy", "fantasy", "farm", "fashion",
    "fat", "fatal", "father", "fatigue", "fault", "favorite", "feature", "february",
    "federal", "fee", "feed", "feel", "female", "fence", "festival", "fetch", "fever",
    "few", "fiber", "fiction", "field", "figure", "file", "film", "filter", "final",
    "find", "fine", "finger", "finish", "fire", "firm", "first", "fiscal", "fish",
    "fit", "fitness", "fix", "flag", "flame", "flash", "flat", "flavor", "flee",
    "flight", "flip", "float", "flock", "floor", "flower", "fluid", "flush", "fly",
    "foam", "focus", "fog", "foil", "fold", "follow", "food", "foot", "force",
    "forest", "forget", "fork", "fortune", "forum", "forward", "fossil", "foster",
    "found", "fox", "fragile", "frame", "frequent", "fresh", "friend", "fringe",
    "frog", "front", "frost", "frown", "frozen", "fruit", "fuel", "fun", "funny",
    "furnace", "fury", "future", "gadget", "gain", "galaxy", "gallery", "game",
    "gap", "garage", "garbage", "garden", "garlic", "garment", "gas", "gasp", "gate",
    "gather", "gauge", "gaze", "general", "genius", "genre", "gentle", "genuine",
    "gesture", "ghost", "giant", "gift", "giggle", "ginger", "giraffe", "girl",
    "give", "glad", "glance", "glare", "glass", "glide", "glimpse", "globe", "gloom",
    "glory", "glove", "glow", "glue", "goat", "goddess", "gold", "good", "goose",
    "gorilla", "gospel", "gossip", "govern", "gown", "grab", "grace", "grain", "grant",
    "grape", "grass", "gravity", "great", "green", "grid", "grief", "grit", "grocery",
    "group", "grow", "grunt", "guard", "guess", "guide", "guilt", "guitar", "gun",
    "gym", "habit", "hair", "half", "hammer", "hamster", "hand", "happy", "harbor",
    "hard", "harsh", "harvest", "hat", "have", "hawk", "hazard", "head", "health",
    "heart", "heavy", "hedgehog", "height", "hello", "helmet", "help", "hen", "hero",
    "hidden", "high", "hill", "hint", "hip", "hire", "history", "hobby", "hockey",
    "hold", "hole", "holiday", "hollow", "home", "honey", "hood", "hope", "horn",
    "horror", "horse", "hospital", "host", "hotel", "hour", "hover", "hub", "huge",
    "human", "humble", "humor", "hundred", "hungry", "hunt", "hurdle", "hurry", "hurt",
    "husband", "hybrid", "ice", "icon", "idea", "identify", "idle", "ignore", "ill",
    "illegal", "illness", "image", "imitate", "immense", "immune", "impact", "impose",
    "improve", "impulse", "inch", "include", "income", "increase", "index", "indicate",
    "indoor", "industry", "infant", "inflict", "inform", "inhale", "inherit", "initial",
    "inject", "injury", "inmate", "inner", "innocent", "input", "inquiry", "insane",
    "insect", "inside", "inspire", "install", "intact", "interest", "into", "invest",
    "invite", "involve", "iron", "island", "isolate", "issue", "item", "ivory", "jacket",
    "jaguar", "jar", "jazz", "jealous", "jeans", "jelly", "jewel", "job", "join",
    "joke", "journey", "joy", "judge", "juice", "jump", "jungle", "junior", "junk",
    "just", "kangaroo", "keen", "keep", "ketchup", "key", "kick", "kid", "kidney",
    "kind", "kingdom", "kiss", "kit", "kitchen", "kite", "kitten", "kiwi", "knee",
    "knife", "knock", "know", "lab", "label", "labor", "ladder", "lady", "lake",
    "lamp", "language", "laptop", "large", "later", "latin", "laugh", "laundry",
    "lava", "law", "lawn", "lawsuit", "layer", "lazy", "leader", "leaf", "learn",
    "leave", "lecture", "left", "leg", "legal", "legend", "leisure", "lemon", "lend",
    "length", "lens", "leopard", "lesson", "letter", "level", "liar", "liberty",
    "library", "license", "life", "lift", "light", "like", "limb", "limit", "link",
    "lion", "liquid", "list", "little", "live", "lizard", "load", "loan", "lobster",
    "local", "lock", "logic", "lonely", "long", "loop", "lottery", "loud", "lounge",
    "love", "loyal", "lucky", "luggage", "lumber", "lunar", "lunch", "luxury", "lyrics",
    "machine", "mad", "magic", "magnet", "maid", "mail", "main", "major", "make",
    "mammal", "man", "manage", "mandate", "mango", "mansion", "manual", "maple",
    "marble", "march", "margin", "marine", "market", "marriage", "mask", "mass",
    "master", "match", "material", "math", "matrix", "matter", "maximum", "maze",
    "meadow", "mean", "measure", "meat", "mechanic", "medal", "media", "melody",
    "melt", "member", "memory", "mention", "menu", "mercy", "merge", "merit", "merry",
    "mesh", "message", "metal", "method", "middle", "midnight", "milk", "million",
    "mimic", "mind", "minimum", "minor", "minute", "miracle", "mirror", "misery",
    "miss", "mistake", "mix", "mixed", "mixture", "mobile", "model", "modify", "mom",
    "moment", "monitor", "monkey", "monster", "month", "moon", "moral", "more",
    "morning", "mosquito", "mother", "motion", "motor", "mountain", "mouse", "move",
    "movie", "much", "muffin", "mule", "multiply", "muscle", "museum", "mushroom",
    "music", "must", "mutual", "myself", "mystery", "myth", "naive", "name", "napkin",
    "narrow", "nasty", "nation", "nature", "near", "neck", "need", "negative", "neglect",
    "neither", "nephew", "nerve", "nest", "net", "network", "neutral", "never", "news",
    "next", "nice", "night", "noble", "noise", "nominee", "noodle", "normal", "north",
    "nose", "notable", "note", "nothing", "notice", "novel", "now", "nuclear", "number",
    "nurse", "nut", "oak", "obey", "object", "oblige", "obscure", "observe", "obtain",
    "obvious", "occur", "ocean", "october", "odor", "off", "offer", "office", "often",
    "oil", "okay", "old", "olive", "olympic", "omit", "once", "one", "onion", "online",
    "only", "open", "opera", "opinion", "oppose", "option", "orange", "orbit", "orchard",
    "order", "ordinary", "organ", "orient", "original", "orphan", "ostrich", "other",
    "outdoor", "outer", "output", "outside", "oval", "oven", "over", "own", "owner",
    "oxygen", "oyster", "ozone", "pact", "paddle", "page", "pair", "palace", "palm",
    "panda", "panel", "panic", "panther", "paper", "parade", "parent", "park", "parrot",
    "party", "pass", "patch", "path", "patient", "patrol", "pattern", "pause", "pave",
    "payment", "peace", "peanut", "pear", "peasant", "pelican", "pen", "penalty",
    "pencil", "people", "pepper", "perfect", "permit", "person", "pet", "phone",
    "photo", "phrase", "physical", "piano", "picnic", "picture", "piece", "pig", "pigeon",
    "pill", "pilot", "pink", "pioneer", "pipe", "pistol", "pitch", "pizza", "place",
    "planet", "plastic", "plate", "play", "please", "pledge", "pluck", "plug", "plunge",
    "poem", "poet", "point", "polar", "pole", "police", "pond", "pony", "pool", "popular",
    "portion", "position", "possible", "post", "potato", "pottery", "poverty", "powder",
    "power", "practice", "praise", "predict", "prefer", "prepare", "present", "pretty",
    "prevent", "price", "pride", "primary", "print", "priority", "prison", "private",
    "prize", "problem", "process", "produce", "profit", "program", "project", "promote",
    "proof", "property", "prosper", "protect", "proud", "provide", "public", "pudding",
    "pull", "pulp", "pulse", "pumpkin", "punch", "pupil", "puppy", "purchase", "purity",
    "purpose", "purse", "push", "put", "puzzle", "pyramid", "quality", "quantum", "quarter",
    "question", "quick", "quit", "quiz", "quote", "rabbit", "raccoon", "race", "rack",
    "radar", "radio", "rail", "rain", "raise", "rally", "ramp", "ranch", "random", "range",
    "rapid", "rare", "rate", "rather", "raven", "raw", "razor", "ready", "real", "reason",
    "rebel", "rebuild", "recall", "receive", "recipe", "record", "recycle", "reduce",
    "reflect", "reform", "refuse", "region", "regret", "regular", "reject", "relax",
    "release", "relief", "rely", "remain", "remember", "remind", "remove", "render",
    "renew", "rent", "reopen", "repair", "repeat", "replace", "report", "require",
    "rescue", "resemble", "resist", "resource", "response", "result", "retire", "retreat",
    "return", "reunion", "reveal", "review", "reward", "rhythm", "rib", "ribbon", "rice",
    "rich", "ride", "ridge", "rifle", "right", "rigid", "ring", "riot", "ripple", "risk",
    "ritual", "rival", "river", "road", "roast", "robot", "robust", "rocket", "romance",
    "roof", "rookie", "room", "rose", "rotate", "rough", "round", "route", "royal",
    "rubber", "rude", "rug", "rule", "run", "runway", "rural", "sad", "saddle", "sadness",
    "safe", "sail", "salad", "salmon", "salon", "salt", "salute", "same", "sample", "sand",
    "satisfy", "satoshi", "sauce", "sausage", "save", "say", "scale", "scan", "scare",
    "scatter", "scene", "scheme", "school", "science", "scissors", "scorpion", "scout",
    "scrap", "screen", "script", "scrub", "sea", "search", "season", "seat", "second",
    "secret", "section", "security", "seed", "seek", "segment", "select", "sell", "seminar",
    "senior", "sense", "sentence", "series", "service", "session", "settle", "setup",
    "seven", "shadow", "shaft", "shallow", "share", "shed", "shell", "sheriff", "shield",
    "shift", "shine", "ship", "shiver", "shock", "shoe", "shoot", "shop", "short", "shoulder",
    "shove", "shrimp", "shrug", "shuffle", "shy", "sibling", "sick", "side", "siege",
    "sight", "sign", "silent", "silk", "silly", "silver", "similar", "simple", "since",
    "sing", "siren", "sister", "situate", "six", "size", "skate", "sketch", "ski", "skill",
    "skin", "skirt", "skull", "slab", "slam", "sleep", "slender", "slice", "slide", "slight",
    "slim", "slogan", "slot", "slow", "slush", "small", "smart", "smile", "smoke", "smooth",
    "snack", "snake", "snap", "sniff", "snow", "soap", "soccer", "social", "sock", "soda",
    "soft", "solar", "soldier", "solid", "solution", "solve", "someone", "song", "soon",
    "sorry", "sort", "soul", "sound", "soup", "source", "south", "space", "spare", "spatial",
    "spawn", "speak", "special", "speed", "spell", "spend", "sphere", "spice", "spider",
    "spike", "spin", "spirit", "split", "spoil", "sponsor", "spoon", "sport", "spot",
    "spray", "spread", "spring", "spy", "square", "squeeze", "squirrel", "stable", "stadium",
    "staff", "stage", "stairs", "stamp", "stand", "start", "state", "stay", "steak", "steel",
    "stem", "step", "stereo", "stick", "still", "sting", "stock", "stomach", "stone", "stool",
    "story", "stove", "strategy", "street", "strike", "strong", "struggle", "student", "stuff",
    "stumble", "style", "subject", "submit", "subway", "success", "such", "sudden", "suffer",
    "sugar", "suggest", "suit", "summer", "sun", "sunny", "sunset", "super", "supply", "supreme",
    "sure", "surface", "surge", "surprise", "surround", "survey", "suspect", "sustain", "swallow",
    "swamp", "swap", "swarm", "swear", "sweet", "swift", "swim", "swing", "switch", "sword",
    "symbol", "symptom", "syrup", "system", "table", "tackle", "tag", "tail", "talent", "talk",
    "tank", "tape", "target", "task", "taste", "tattoo", "taxi", "teach", "team", "tell", "ten",
    "tenant", "tennis", "tent", "term", "test", "text", "thank", "that", "theme", "then", "theory",
    "there", "they", "thing", "this", "thought", "three", "thrive", "throw", "thumb", "thunder",
    "ticket", "tide", "tiger", "tilt", "timber", "time", "tiny", "tip", "tired", "tissue", "title",
    "toast", "tobacco", "today", "toddler", "toe", "together", "toilet", "token", "tomato", "tomorrow",
    "tone", "tongue", "tonight", "tool", "tooth", "top", "topic", "topple", "torch", "tornado", "tortoise",
    "toss", "total", "tourist", "toward", "tower", "town", "toy", "track", "trade", "traffic", "tragic",
    "train", "transfer", "trap", "trash", "travel", "tray", "treat", "tree", "trend", "trial", "tribe",
    "trick", "trigger", "trim", "trip", "trophy", "trouble", "truck", "true", "truly", "trumpet", "trust",
    "truth", "try", "tube", "tuition", "tumble", "tuna", "tunnel", "turkey", "turn", "turtle", "twelve",
    "twenty", "twice", "twin", "twist", "two", "type", "typical", "ugly", "umbrella", "unable", "unaware",
    "uncle", "uncover", "under", "undo", "unfair", "unfold", "unhappy", "uniform", "unique", "unit", "universe",
    "unknown", "unlock", "until", "unusual", "unveil", "update", "upgrade", "uphold", "upon", "upper", "upset",
    "urban", "urge", "usage", "use", "used", "useful", "useless", "usual", "utility", "vacant", "vacuum",
    "vague", "valid", "valley", "valve", "van", "vanish", "vapor", "various", "vast", "vault", "vehicle", "velvet",
    "vendor", "venture", "venue", "verb", "verify", "version", "very", "vessel", "veteran", "viable", "vibrant",
    "vicious", "victory", "video", "view", "village", "vintage", "violin", "virtual", "virus", "visa", "visit",
    "visual", "vital", "vivid", "vocal", "voice", "void", "volcano", "volume", "vote", "voyage", "wage", "wagon",
    "wait", "walk", "wall", "walnut", "want", "warfare", "warm", "warrior", "wash", "wasp", "waste", "water",
    "wave", "way", "wealth", "weapon", "wear", "weasel", "weather", "web", "wedding", "weekend", "weird", "welcome",
    "west", "wet", "whale", "what", "wheat", "wheel", "when", "where", "whip", "whisper", "wide", "width", "wife",
    "wild", "will", "win", "window", "wine", "wing", "wink", "winner", "winter", "wire", "wisdom", "wise", "wish",
    "witness", "wolf", "woman", "wonder", "wood", "wool", "word", "work", "world", "worry", "worth", "wrap", "wreck",
    "wrestle", "wrist", "write", "wrong", "yard", "year", "yellow", "you", "young", "youth", "zebra", "zero", "zone", "zoo"
]


def generate_phrase(word_count=12):
    """
    Generate a random BIP-39 style recovery phrase.
    Uses secrets.SystemRandom for cryptographic randomness.
    Words are unique (no duplicates).
    """
    rng = secrets.SystemRandom()
    words = rng.sample(BIP39_WORDS, word_count)
    return ' '.join(words)


def validate_phrase(phrase, word_count=None):
    """
    Validate that a phrase consists of BIP-39 words.
    Returns True if all words are in the list (or word_count matches if provided).
    """
    words = phrase.lower().split()
    if word_count and len(words) != word_count:
        return False
    for w in words:
        if w not in BIP39_WORDS:
            return False
    return True


# ============================================================================
# MAIN CRYPTO CLASS
# ============================================================================

class Crypto:
    _session_storage = None  # Class-level storage for secure session
    
    def __init__(self, password_key, phrase_key, folder_name):
        if not HAS_CRYPTO:
            raise Exception("Cryptography library not available")
        
        self.password_key = password_key
        self.phrase_key = phrase_key
        self.folder_name = folder_name
        
        # For combined key verification
        if password_key is not None and phrase_key is not None:
            self.combined_key = combine_keys(password_key, phrase_key)
        else:
            self.combined_key = None
        
        # For decryption, use phrase_key if available, otherwise password_key
        if phrase_key is not None:
            self.key = phrase_key
        elif password_key is not None:
            self.key = password_key
        else:
            self.key = None
        
        if self.key is not None:
            self.aesgcm = AESGCM(self.key)
        else:
            self.aesgcm = None

    
    @classmethod
    def from_password(cls, password, folder_name):
        """
        Create crypto from password only (for password-only notebooks).
        In this mode, phrase_key = password_key.
        """
        password_key = derive_key(password, folder_name)
        return cls(password_key, password_key, folder_name)
    
    @classmethod
    def from_password_and_phrase(cls, password, phrase, folder_name):
        """Create crypto from both password and phrase."""
        password_key = derive_key(password, folder_name)
        phrase_key = derive_key(phrase, folder_name)
        return cls(password_key, phrase_key, folder_name)
    
    @classmethod
    def retrieve_for_folder(cls, folder_identifier):
        """
        Retrieve a Crypto instance for a folder from permanent storage.
        This is used by load_all_notebooks() to get keys for encrypted notebooks.
        
        Args:
            folder_identifier: The folder name (e.g., "notebookname-20260331100124")
        
        Returns:
            Crypto instance with loaded keys, or None if not found
        """
        if not HAS_CRYPTO:
            return None
        
        # Initialize session storage if needed
        if cls._session_storage is None:
            import sys
            import os
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.abspath(__file__))
            cls._session_storage = SecureSessionStorage(app_dir)
        
        # Extract notebook_id from folder_identifier (format: name-id)
        if '-' in folder_identifier:
            notebook_id = folder_identifier.split('-')[-1]
        else:
            notebook_id = folder_identifier
        
        # Get keys from secure session
        password_key, phrase_key = cls._session_storage.get_keys(notebook_id)
        
        if password_key is None or phrase_key is None:
            return None
        
        # Create crypto instance with the retrieved keys
        instance = cls.__new__(cls)
        instance.password_key = password_key
        instance.phrase_key = phrase_key
        instance.folder_name = folder_identifier
        instance.combined_key = combine_keys(password_key, phrase_key)
        instance.key = phrase_key
        instance.aesgcm = AESGCM(phrase_key)
        
        return instance
    
    # ========================================================================
    # ENCRYPTION/DECRYPTION METHODS
    # ========================================================================
    
    def encrypt(self, data):
        """Encrypt data with phrase_key (for notebook content)."""
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
        elif isinstance(data, bytes):
            data_bytes = data
        else:
            data_bytes = str(data).encode('utf-8')
        
        # Add magic header
        magic = b"TN_ENC"
        data_with_magic = magic + data_bytes
        
        # Generate random 12-byte nonce
        nonce = os.urandom(12)
        
        # Encrypt with phrase_key
        aesgcm = AESGCM(self.phrase_key)
        ciphertext = aesgcm.encrypt(nonce, data_with_magic, None)
        
        return nonce + ciphertext
    
    def decrypt(self, encrypted_data):
        """Decrypt data with available key"""
        if not encrypted_data:
            return None
        
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        
        # Try with phrase_key first
        if self.phrase_key is not None:
            try:
                aesgcm = AESGCM(self.phrase_key)
                plaintext = aesgcm.decrypt(nonce, ciphertext, None)
                if plaintext.startswith(b"TN_ENC"):
                    return plaintext[6:].decode('utf-8')
            except:
                pass
        
        # Try with password_key
        if self.password_key is not None and self.password_key != self.phrase_key:
            try:
                aesgcm = AESGCM(self.password_key)
                plaintext = aesgcm.decrypt(nonce, ciphertext, None)
                if plaintext.startswith(b"TN_ENC"):
                    return plaintext[6:].decode('utf-8')
            except:
                pass
        
        # Try with self.key
        if self.key is not None:
            aesgcm = AESGCM(self.key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            if not plaintext.startswith(b"TN_ENC"):
                raise ValueError("Invalid key - magic header not found")
            return plaintext[6:].decode('utf-8')
        
        raise ValueError("No key available for decryption")

    
    def encrypt_with_combined(self, data):
        """Encrypt data with combined_key (for .tn_password file)."""
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
        elif isinstance(data, bytes):
            data_bytes = data
        else:
            data_bytes = str(data).encode('utf-8')
        
        nonce = os.urandom(12)
        aesgcm = AESGCM(self.combined_key)
        ciphertext = aesgcm.encrypt(nonce, data_bytes, None)
        return nonce + ciphertext
    
    def decrypt_with_combined(self, encrypted_data):
        """Decrypt data with combined_key."""
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        aesgcm = AESGCM(self.combined_key)
        return aesgcm.decrypt(nonce, ciphertext, None)
    
    def encrypt_with_password(self, data):
        """Encrypt data with password_key."""
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
        elif isinstance(data, bytes):
            data_bytes = data
        else:
            data_bytes = str(data).encode('utf-8')
        
        nonce = os.urandom(12)
        aesgcm = AESGCM(self.password_key)
        ciphertext = aesgcm.encrypt(nonce, data_bytes, None)
        return nonce + ciphertext
    
    def decrypt_with_password(self, encrypted_data):
        """Decrypt data with password_key."""
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        aesgcm = AESGCM(self.password_key)
        return aesgcm.decrypt(nonce, ciphertext, None)
    
    def encrypt_file(self, filepath):
        """Encrypt a file in-place using phrase_key."""
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            
            encrypted = self.encrypt(data)
            
            with open(filepath, 'wb') as f:
                f.write(encrypted)
        except Exception as e:
            raise
    
    def decrypt_file(self, filepath):
        """Decrypt a file in-place using phrase_key."""
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            
            decrypted = self.decrypt(data)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(decrypted)
        except Exception as e:
            raise
    
    # ========================================================================
    # RECOVERY FILE OPERATIONS
    # ========================================================================
    
    def create_recovery_file(self, filepath, password_hash, password_key):
        """
        Create .tn_recovery file.
        Contains password_hash and password_key, encrypted with phrase_key.
        """
        recovery_data = {
            "password_hash": password_hash,
            "password_key": password_key.hex() if isinstance(password_key, bytes) else password_key
        }
        json_str = json.dumps(recovery_data)
        encrypted = self.encrypt(json_str)  # Uses phrase_key
        with open(filepath, 'wb') as f:
            f.write(encrypted)
    
    def read_recovery_file(self, filepath):
        """
        Read and decrypt .tn_recovery file.
        Returns (password_hash, password_key) or None.
        """
        try:
            with open(filepath, 'rb') as f:
                encrypted = f.read()
            json_str = self.decrypt(encrypted)  # Uses phrase_key
            data = json.loads(json_str)
            password_key = bytes.fromhex(data["password_key"]) if isinstance(data["password_key"], str) else data["password_key"]
            return data["password_hash"], password_key
        except Exception:
            return None, None
    
    def create_password_file(self, filepath):
        """
        Create .tn_password file.
        Contains the combined_key itself, encrypted with combined_key (self-referential).
        """
        password_data = {
            "combined_key": self.combined_key.hex()
        }
        json_str = json.dumps(password_data)
        encrypted = self.encrypt_with_combined(json_str)  # Uses combined_key
        with open(filepath, 'wb') as f:
            f.write(encrypted)
    
    def verify_password_file(self, filepath):
        """
        Verify .tn_password file.
        Decrypts and checks that the stored combined_key matches current.
        Returns True if valid.
        """
        try:
            with open(filepath, 'rb') as f:
                encrypted = f.read()
            decrypted = self.decrypt_with_combined(encrypted)
            data = json.loads(decrypted.decode('utf-8'))
            stored_key = bytes.fromhex(data["combined_key"])
            return stored_key == self.combined_key
        except Exception:
            return False
    
    # ========================================================================
    # TEST MARKER OPERATIONS
    # ========================================================================
    
    def create_test_marker(self, filepath, test_string="VERIFICATION"):
        """Create .tn_test marker file encrypted with phrase_key."""
        encrypted = self.encrypt(test_string)
        with open(filepath, 'wb') as f:
            f.write(encrypted)
    
    def verify_test_marker(self, filepath):
        """Verify .tn_test marker file."""
        try:
            with open(filepath, 'rb') as f:
                encrypted = f.read()
            decrypted = self.decrypt(encrypted)
            return decrypted is not None
        except Exception:
            return False
    
    def is_encrypted(self, filepath):
        """Check if a file is encrypted (has TN_ENC magic header)."""
        try:
            with open(filepath, 'rb') as f:
                data = f.read(10)
            return data.startswith(b'TN_ENC')
        except Exception:
            return False
    
    def decrypt(self, encrypted_data):
        if not encrypted_data:
            return None
        
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        
        if self.phrase_key is not None:
            try:
                aesgcm = AESGCM(self.phrase_key)
                plaintext = aesgcm.decrypt(nonce, ciphertext, None)
                if plaintext.startswith(b"TN_ENC"):
                    return plaintext[6:].decode('utf-8')
            except Exception:
                pass
        
        if self.password_key is not None and self.password_key != self.phrase_key:
            try:
                aesgcm = AESGCM(self.password_key)
                plaintext = aesgcm.decrypt(nonce, ciphertext, None)
                if plaintext.startswith(b"TN_ENC"):
                    return plaintext[6:].decode('utf-8')
            except Exception:
                pass
        
        if self.key is not None:
            aesgcm = AESGCM(self.key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            if not plaintext.startswith(b"TN_ENC"):
                raise ValueError("Invalid key - magic header not found")
            return plaintext[6:].decode('utf-8')
        
        raise ValueError("No key available for decryption")