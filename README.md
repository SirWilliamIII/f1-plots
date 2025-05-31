#### DEMO here [https://f1-plots.app](https://f1-plots.app)

## Either do this

### 1. Clone the repository

```sh
git clone https://github.com/yourusername/f1-race-plots.git
cd f1-race-plots
```

### 2. Install dependencies

```sh
pip install -r requirements.txt
```

### 3. Run the app

```sh
python app.py
```

The app will be available at [http://127.0.0.1:5000](http://127.0.0.1:5000).

---

## Or just...

### Build and run with Docker:

```sh
docker build -t f1-race-plots .
docker run -p 8080:8080 f1-race-plots
```
Then visit [http://localhost:8080](http://localhost:8080).

---


## Credits

- [FastF1](https://theoehrly.github.io/Fast-F1/)
- [Flask](https://flask.palletsprojects.com/)
