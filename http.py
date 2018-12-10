from flask import Flask, render_template, redirect
app = Flask(__name__)

@app.route('/')
def hello_world():
    return render_template('index.html')

@app.route('/post', methods = ['POST'])
def Start():
    print("Starting")
    return redirect('/')

if __name__ == '__main__':
    app.run()
