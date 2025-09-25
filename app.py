from flask import Flask,request,render_template

app=Flask(__name__)

@app.route("/")
def main():
    return render_template("index.html")

@app.route("/log",methods=["GET","POST"])
def log_function():
    if request.method=="POST":
        name=request.form.get("name")
        if name :
            return render_template("welcome.html",name=name)
    return render_template("log.html")

if __name__=="__main__":
    app.run(debug=True)
