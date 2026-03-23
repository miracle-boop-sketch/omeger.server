from flask import Flask, render_template, request, redirect, session, jsonify
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker
import os

app = Flask(__name__)
app.secret_key = "omega_secret"

# --- DATABASE ---
engine = create_engine("sqlite:///omega.db")
Base = declarative_base()
DBSession = sessionmaker(bind=engine)
db = DBSession()

# --- MODELS ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)
    role = Column(String, default="restricted")

class File(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    content = Column(Text, default="")

Base.metadata.create_all(engine)

# --- INIT ADMIN ---
def init():
    if not db.query(User).filter_by(username="admin").first():
        db.add(User(username="admin", password="1234", role="admin"))
        db.commit()

init()

# --- COMMAND SYSTEM ---
COMMANDS = {}

def command(name, role="restricted"):
    def wrapper(func):
        COMMANDS[name] = {"func": func, "role": role}
        return func
    return wrapper

def parse_command(input_str):
    parts = input_str.strip().split()
    if not parts:
        return None, []
    return parts[0], parts[1:]

def execute(user, input_str):
    outputs = []
    commands = input_str.split(";")

    for cmd in commands:
        name, args = parse_command(cmd)

        if name not in COMMANDS:
            outputs.append(f"Unknown command: {name}")
            continue

        if user.role != "admin" and COMMANDS[name]["role"] == "admin":
            outputs.append("Permission denied")
            continue

        try:
            result = COMMANDS[name]["func"](user, args)
            outputs.append(result)
        except Exception as e:
            outputs.append(f"Error: {str(e)}")

    return "\n".join(outputs)

# --- COMMANDS ---
@command("help")
def help_cmd(user, args):
    return "help, clear, echo, ls, touch, cat, write, rm"

@command("echo")
def echo(user, args):
    return " ".join(args)

@command("ls")
def ls(user, args):
    files = db.query(File).all()
    return "\n".join([f.name for f in files]) or "empty"

@command("touch")
def touch(user, args):
    name = args[0]
    db.add(File(name=name))
    db.commit()
    return f"created {name}"

@command("cat")
def cat(user, args):
    f = db.query(File).filter_by(name=args[0]).first()
    if not f:
        return "file not found"
    return f.content

@command("write")
def write(user, args):
    name = args[0]
    content = " ".join(args[1:])

    f = db.query(File).filter_by(name=name).first()
    if not f:
        return "file not found"

    f.content = content
    db.commit()
    return "written"

@command("rm")
def rm(user, args):
    f = db.query(File).filter_by(name=args[0]).first()
    if not f:
        return "file not found"

    db.delete(f)
    db.commit()
    return "deleted"

# --- ROUTES ---
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = db.query(User).filter_by(
            username=request.form["username"],
            password=request.form["password"]
        ).first()

        if user:
            session["user"] = user.username
            return redirect("/dashboard")

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    user = db.query(User).filter_by(username=session["user"]).first()
    return render_template("dashboard.html", user=user.username)

@app.route("/command", methods=["POST"])
def command_route():
    if "user" not in session:
        return {"error": "unauthorized"}

    user = db.query(User).filter_by(username=session["user"]).first()
    cmd = request.json.get("command")

    result = execute(user, cmd)
    return {"response": result}

# --- RUN ---
port = int(os.environ.get("PORT", 3000))
app.run(host="0.0.0.0", port=port)