from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
import sqlite3, os, datetime
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    import subprocess
    subprocess.check_call(["pip", "install", "playwright"])
    from playwright.sync_api import sync_playwright

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'baller'
please_please_just_fucking_Store_it = None
db = SQLAlchemy(app)
migrate = Migrate(app, db)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    height = db.Column(db.Integer)
    weight = db.Column(db.Integer)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    activity_level = db.Column(db.String(10))
    adjustment_pace = db.Column(db.String(10))
    direction = db.Column(db.String(15))
    calorie_goal = db.Column(db.Integer)
    protein_goal = db.Column(db.Integer)
    carbohydrates_limit = db.Column(db.Integer)
    fats_limit = db.Column(db.Integer)
    sugar_limit = db.Column(db.Integer)
    
    calories_consumed = 0
    calories_left = 0
    protein_left = 0
    protein_consumed = 0
    carbohydrates_consumed = 0
    carbohydrates_left = 0
    fats_consumed = 0
    fats_left = 0
    sugar_consumed = 0
    sugar_left = 0

def calculate_nutritional_goals(user):
    # Constants for calorie calculation
    # bmr should be rmr and is the resting metabolic rate using the mifflin-st jeor equation
    MALE_BMR_CONSTANT = 5
    FEMALE_BMR_CONSTANT = 161
    ACTIVITY_LEVEL_MULTIPLIER = {
        'sedentary': 1.2,
        'moderate': 1.55,
        'active': 1.9
    }

    adjustment_levels = {
        'moderate': 300,
        'fast': 500,
        'slow': 100
    }

    if user.gender.lower() == 'male':
        bmr = (10 * user.weight) + (6.25 * user.height) - (5 * user.age) + MALE_BMR_CONSTANT
    elif user.gender.lower() == 'female':
        bmr = (10 * user.weight) + (6.25 *user.height) - (5 * user.age) - FEMALE_BMR_CONSTANT

    activity_multiplier = ACTIVITY_LEVEL_MULTIPLIER.get(user.activity_level.lower(), 1)
    adjustment_value = adjustment_levels.get(user.adjustment_pace.lower())
    calorie_goal = int(bmr * activity_multiplier)
    if user.direction == 'weight_gain':
        calorie_goal += adjustment_value
    elif user.direction == 'weight_loss':
        calorie_goal -= adjustment_value

    protein_goal = user.weight * 0.8 

    fats_limit = 0.25 * calorie_goal / 9

    carbohydrates_limit = 0.55 * calorie_goal / 4

    sugar_limit = 0.1 * calorie_goal / 4

    return {
        'calorie_goal': int(calorie_goal),
        'protein_goal': int(protein_goal),
        'fats_limit': int(fats_limit),
        'carbohydrates_limit': int(carbohydrates_limit),
        'sugar_limit': int(sugar_limit)
    }


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/dashboard", methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        day_multiplier = 1
        if request.json["task"] == 'timeframe':
            #1, 7, 30
            day_multiplier = request.json["data"]
        
        conn = sqlite3.connect('db.sqlite3')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT Date
            FROM UserIntake
            WHERE UserID = ?
        """, (current_user.id,))
        date_data = cursor.fetchall()

        json_data = {
            "intake_data_week": [
            {
              "name": "Carbohydrates",
              "data": [],
            },
            {
              "name": "Fats",
              "data": [],
            },
            {
              "name": "Sugar",
              "data": [],
            },
            {
              "name": "Protein",
              "data": [],
            },
            {
              "name": "Calories",
              "data": [],
            }],
            "calories_consumed": 0,
            "calories_left": 0,
            "protein_consumed": 0,
            "protein_left": 0,
            "carbohydrates_consumed": 0,
            "carbohydrates_left": 0,
            "fats_consumed": 0,
            "fats_left": 0,
            "sugar_consumed": 0,
            "sugar_left": 0,
            "calorie_goal": current_user.calorie_goal*day_multiplier,
            "protein_goal": current_user.protein_goal*day_multiplier,
            "carbohydrates_limit": current_user.carbohydrates_limit*day_multiplier,
            "fats_limit": current_user.fats_limit*day_multiplier,
            "sugar_limit": current_user.sugar_limit*day_multiplier,
            "dates": [],
            "change_message": "",
            "food": {
                "name": "",
                "carbohydrate": 0,
                "protein": 0,
                "sugar": 0,
                "fat": 0,
                "calories": 0
            }
        }
        
        for date in date_data:
            date = date[0]
            realdate = datetime.datetime.strptime(date, '%Y-%m-%d')
            # this is = to 7 if multiplier is = to 1 so the line graph shows 7 data points when set to today otherwise it shows nothing
            if (realdate + datetime.timedelta(days=0)).date() >= (datetime.datetime.today() - datetime.timedelta(days = 7 if day_multiplier == 1 else day_multiplier)).date():
                json_data["dates"].append(date)
                cursor.execute("""
                    SELECT UserIntake.FoodID, Date, DailyCalories, DailyProtein, DailyCarbohydrates,
                        DailyFats, DailySugar
                    FROM UserIntake
                    JOIN food ON UserIntake.FoodID = food.FoodID
                    WHERE UserID = ? AND Date = ?
                    ORDER BY Date ASC
                """, (current_user.id, date))
                intake_data = cursor.fetchall()

                calories, protein, carbohydrates, fats, sugar = 0, 0, 0, 0, 0
                for entry in intake_data:
                    calories += entry[2]
                    protein += entry[3]
                    carbohydrates += entry[4]
                    fats += entry[5]
                    sugar += entry[6]
                
                if (realdate + datetime.timedelta(days=0)).date() >= (datetime.datetime.today() - datetime.timedelta(days = 0 if day_multiplier == 1 else day_multiplier)).date():
                    json_data['calories_consumed'] += round(calories)
                    json_data['protein_consumed'] += round(protein)
                    json_data['carbohydrates_consumed'] += round(carbohydrates)
                    json_data['fats_consumed'] += round(fats)
                    json_data['sugar_consumed'] += round(sugar)
                # creating the linechart data points, if greater than 1, cumulative, otherwise individual
                if day_multiplier > 1:
                    json_data["intake_data_week"][4]["data"].append(round(json_data['calories_consumed']/json_data['calorie_goal'] * 100))
                    json_data["intake_data_week"][3]["data"].append(round(json_data['protein_consumed']/json_data['protein_goal'] * 100))
                    json_data["intake_data_week"][0]["data"].append(round(json_data['carbohydrates_consumed']/json_data['carbohydrates_limit'] * 100))
                    json_data["intake_data_week"][1]["data"].append(round(json_data['fats_consumed']/json_data['fats_limit'] * 100))
                    json_data["intake_data_week"][2]["data"].append(round(json_data['sugar_consumed']/json_data['sugar_limit'] * 100))
                else:
                    json_data["intake_data_week"][4]["data"].append(round(calories/json_data['calorie_goal'] * 100))
                    json_data["intake_data_week"][3]["data"].append(round(protein/json_data['protein_goal'] * 100))
                    json_data["intake_data_week"][0]["data"].append(round(carbohydrates/json_data['carbohydrates_limit'] * 100))
                    json_data["intake_data_week"][1]["data"].append(round(fats/json_data['fats_limit'] * 100))
                    json_data["intake_data_week"][2]["data"].append(round(sugar/json_data['sugar_limit'] * 100))
                
        json_data['calories_left'] = round(json_data['calories_consumed']/json_data['calorie_goal'] * 100)
        json_data['protein_left'] = round(json_data['protein_consumed']/json_data['protein_goal'] * 100)
        json_data['carbohydrates_left'] = round(json_data['carbohydrates_consumed']/json_data['carbohydrates_limit'] * 100)
        json_data['fats_left'] = round(json_data['fats_consumed']/json_data['fats_limit'] * 100)
        json_data['sugar_left'] = round(json_data['sugar_consumed']/json_data['sugar_limit'] * 100)
        try: 
            change = json_data['calories_left'] - round(json_data["intake_data_week"][4]["data"][-2])
            
            last_meal = intake_data[-1][0]
            cursor.execute("SELECT * FROM food WHERE FoodID = ?", (last_meal,))
            food_details = cursor.fetchone()
            if food_details:
                protein = food_details[4]
                carbohydrates = food_details[3]
                fats = food_details[6]
                sugar = food_details[5]
                calories = protein * 4 + carbohydrates * 4 + fats * 9 + sugar * 4
                json_data["food"] = {
                    'name': food_details[1],
                    'carbohydrate': carbohydrates,
                    'protein': protein,
                    'sugar': sugar,
                    'fat': fats,
                    'calories': round(calories)
                }
        except IndexError: change = 0
        
        if day_multiplier <= 1:
            past = "yesterday"
        elif day_multiplier == 7:
            past = "last week"
        else:
            past = "last month"
        
        if change > 0:
            json_data["change_message"] = f"{change}% worse than {past}"
        elif change < 0:
            json_data["change_message"] = f"{abs(change)}% better than {past}"

        conn.close()
        
        return jsonify(json_data)
        
    try:
        # Fetch user's personal information
        user_data = {
            "username": current_user.username,
        }
        
        return render_template("dashboard.html", user_data=user_data)
    
    except Exception as e:
        return jsonify({'success': False, 'error': 'An error occurred while fetching data: ' + str(e)})
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            goals = calculate_nutritional_goals(user)
            current_user.calorie_goal = goals["calorie_goal"]
            current_user.protein_goal = goals["protein_goal"]
            current_user.fats_limit = goals["fats_limit"]
            current_user.carbohydrates_limit = goals["carbohydrates_limit"]
            current_user.sugar_limit = goals["sugar_limit"]
            db.session.commit()
            return redirect(url_for('dashboard'))
        else: return redirect(url_for('home'))

    return render_template('login.html')

from flask_login import current_user

@app.route("/addfood", methods=['GET', 'POST'])
@login_required
def addfood():
    if request.method == 'POST':
        user_id = current_user.id  # Assuming the current user is logged in
        data = request.json
        food_id = data.get('food_id')
        meal_type = data.get('meal_type')
        
        if food_id is None or meal_type is None:
            return jsonify({'success': False, 'error': 'Food ID and meal type are required.'}), 400
        
        date = datetime.date.today()
        food_details = fetch_food_details(food_id)
        if food_details.get('error'):
            return jsonify({'success': False, 'error': food_details['error']})
        
        quantity = data.get('quantity', 1)
        calories = food_details['calories'] * float(quantity)
        protein = food_details['protein'] * float(quantity)
        carbohydrates = food_details['carbohydrate'] * float(quantity)
        fats = food_details['fat'] * float(quantity)
        sugar = food_details['sugar'] * float(quantity)
        try:
            conn = sqlite3.connect('db.sqlite3')
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO UserIntake (UserID, FoodID, MealType, Date, DailyCalories, DailyProtein,
                                        DailyCarbohydrates, DailyFats, DailySugar)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, food_id, meal_type, date, calories, protein, carbohydrates, fats, sugar))
            conn.commit()
            conn.close()

            # Update current_user attributes
            current_user.calories_consumed += calories
            current_user.protein_consumed += protein
            current_user.carbohydrates_consumed += carbohydrates
            current_user.fats_consumed += fats
            current_user.sugar_consumed += sugar
            
            # Reduce the limits
            current_user.calories_left -= calories
            current_user.protein_left -= protein
            current_user.carbohydrates_left -= carbohydrates
            current_user.fats_left -= fats
            current_user.sugar_left -= sugar

            return jsonify({
                'success': True,
                'message': 'Food entry added successfully.',
                'calories': calories,
                'protein': protein,
                'carbohydrates': carbohydrates,
                'fats': fats,
                'sugar': sugar
            }), 200
        except Exception as e:
            print(e)
            return jsonify({'success': False, 'error': 'An error occurred while adding the food entry: ' + str(e)}), 500
    
    return render_template("addfood.html")

@app.route('/pdf', methods=['GET'])
def pdf_template():
    user_data = please_please_just_fucking_Store_it
    
    return render_template('pdf_template.html', user_data=user_data)

@app.route('/pdf/download', methods=['GET'])
def send_pdf():
    global please_please_just_fucking_Store_it
    user_data = process_graph_data(request.args.get("start_date"), request.args.get("end_date"))
    user_data["username"] = current_user.username
    user_data["age"] = current_user.age
    user_data["sex"] = current_user.gender
    user_data["height"] = current_user.height
    user_data["weight"] = current_user.weight
    user_data["activity_level"] = current_user.activity_level
    user_data["adjustment_pace"] = current_user.adjustment_pace
    
    # this is so jank i might just kill myself
    please_please_just_fucking_Store_it = user_data
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="msedge")
        page = browser.new_page()
        page.goto(url_for("pdf_template", _external=True))
        page.pdf(path=f'./static/pdfs/{current_user.id}.pdf')

    return send_from_directory(os.path.join(app.root_path, './static/pdfs/'), f"{current_user.id}.pdf")

@app.route('/search', methods=['GET'])
def search():
    conn = sqlite3.connect('db.sqlite3')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM food")
    results = cursor.fetchall()
    conn.close()
    return jsonify(results)

def fetch_food_details(nutrition_bank_id):
    conn = sqlite3.connect('db.sqlite3')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM food WHERE FoodID = ?", (nutrition_bank_id,))
    food_details = cursor.fetchone()
    conn.close()
    if food_details:
        protein = food_details[4]
        carbohydrates = food_details[3]
        fats = food_details[6]
        sugar = food_details[5]
        
        calories = protein * 4 + carbohydrates * 4 + fats * 9 + sugar * 4
        return {
            'name': food_details[1],
            'carbohydrate': carbohydrates,
            'protein': protein,
            'sugar': sugar,
            'fat': fats,
            'calories': calories
        }
    else:
        return {'error': 'Food not found'}

@app.route('/food/<int:nutrition_bank_id>')
def get_food_details(nutrition_bank_id):
    food_details = fetch_food_details(nutrition_bank_id)
    if 'error' in food_details:
        return jsonify(food_details), 404
    else:
        return jsonify(food_details)

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        height = request.form['height']
        weight = request.form['weight']
        age = request.form['age']
        gender = request.form['gender']
        activity_level = request.form['activity_level']
        adjustment_pace = request.form['adjustment_pace']
        direction = request.form['direction']

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        try:
            new_user = User(username=username, password=hashed_password, height=height, weight=weight,
                            age=age, gender=gender, activity_level=activity_level,
                            adjustment_pace=adjustment_pace, direction=direction)

            db.session.add(new_user)
            db.session.commit()

            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('login'))

        except IntegrityError:
            db.session.rollback()
            flash('Username already exists. Please choose a different username.', 'danger')

    return render_template("register.html")

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if request.method == 'POST':
        current_user.username = request.form['username']
        current_user.age = int(request.form['age'])
        current_user.gender = request.form['gender']
        current_user.height = float(request.form['height'])
        current_user.weight = float(request.form['weight'])
        current_user.activity_level = request.form['activity_level']
        current_user.direction = request.form['direction']
        current_user.adjustment_pace = request.form['adjustment_pace']
        goals = calculate_nutritional_goals(current_user)
        current_user.calorie_goal = goals["calorie_goal"]
        current_user.protein_goal = goals["protein_goal"]
        current_user.fats_limit = goals["fats_limit"]
        current_user.carbohydrates_limit = goals["carbohydrates_limit"]
        current_user.sugar_limit = goals["sugar_limit"]
        
        db.session.commit()
        return redirect(url_for('dashboard'))

@app.route("/searchfood")
def searchfood():
    return render_template("searchfood.html")

@app.route("/graphs", methods=['POST', 'GET'])
@login_required
def graphs():
    if request.method == 'POST':
        start_date = request.json["start_date"]
        end_date = request.json["end_date"]
     
        data = process_graph_data(start_date, end_date)
        
        return data
        
    return render_template("graphs.html")

def process_graph_data(start_date, end_date):
    if start_date:
        start_date = datetime.datetime.strptime(start_date, '%m/%d/%Y')
        end_date = datetime.datetime.strptime(end_date, '%m/%d/%Y')
    else:
        start_date = datetime.datetime.today() - datetime.timedelta(days=21)
        end_date = datetime.datetime.today()   
    days = (end_date - start_date).days
            
    conn = sqlite3.connect('db.sqlite3')
    cursor = conn.cursor()

    cursor.execute("""
            SELECT Date, DailyCalories, DailyProtein, DailyCarbohydrates,
                   DailyFats, DailySugar
            FROM UserIntake
            JOIN food ON UserIntake.FoodID = food.FoodID
            WHERE UserID = ? AND Date >= ? AND Date <= ?
            ORDER BY Date DESC
        """, (current_user.id, start_date.date(), end_date.date()))
    intake_data = cursor.fetchall()
    data = {
            "bar_chart": {
                "calories": [{"name": "Intake", "data": []}, {"name": "Remaining/Over", "data": []}],
                "protein": [{"name": "Intake", "data": []}, {"name": "Remaining/Over", "data": []}],
                "carbohydrates": [{"name": "Intake", "data": []}, {"name": "Remaining/Over", "data": []}],
                "fats": [{"name": "Intake", "data": []}, {"name": "Remaining/Over", "data": []}],
                "sugar": [{"name": "Intake", "data": []}, {"name": "Remaining/Over", "data": []}],
            }
        }
    conn.close()

    # i hate all of this but it works
    calories, protein, carbohydrates, fats, sugar, date = 0, 0, 0, 0, 0, 0
    colour_normal = "#a6a6a6"
    colour_over = "#4d194d"
    intake_data.reverse()
    intake_data.append([-1])

    calorie_goal = current_user.calorie_goal or 2400
    protein_limit = current_user.protein_goal or 70
    carbohydrates_limit = current_user.carbohydrates_limit or 300
    fats_limit = current_user.fats_limit or 78
    sugar_limit = current_user.sugar_limit or 50
    total_calories, total_protein, total_carbohydrates, total_fats, total_sugar = 0, 0, 0, 0, 0

    for num, entry in enumerate(intake_data):
            # checks if the date of the next line is different, if it is thats the end of the records for that day
            # so appends them and moves on to the next date
        if entry[0] != date and num != 0:
            calorie_diff = calorie_goal - calories
            data["bar_chart"]['calories'][0]["data"].append({"x": date, "y": calories if calories < calorie_goal else calorie_goal, "the_goal": calorie_goal})
            data["bar_chart"]['calories'][1]["data"].append({"x": date, "y": abs(calorie_diff), "fillColor": colour_over if calorie_diff < 0 else colour_normal})
            protein_diff = protein_limit - protein
            data["bar_chart"]['protein'][0]["data"].append({"x": date, "y": protein if protein < protein_limit else protein_limit, "the_goal": protein_limit})
            data["bar_chart"]['protein'][1]["data"].append({"x": date, "y": abs(protein_diff), "fillColor": colour_over if protein_diff < 0 else colour_normal})
            carb_diff = carbohydrates_limit - carbohydrates
            data["bar_chart"]['carbohydrates'][0]["data"].append({"x": date, "y": carbohydrates if carbohydrates < carbohydrates_limit else carbohydrates_limit,
                                                        "the_goal": carbohydrates_limit})
            data["bar_chart"]['carbohydrates'][1]["data"].append({"x": date, "y": abs(carb_diff), "fillColor": colour_over if carb_diff < 0 else colour_normal})
            fat_diff = fats_limit - fats
            data["bar_chart"]['fats'][0]["data"].append({"x": date, "y": fats if fats < fats_limit else fats_limit, "the_goal": fats_limit})
            data["bar_chart"]['fats'][1]["data"].append({"x": date, "y": abs(fat_diff), "fillColor": colour_over if fat_diff < 0 else colour_normal})
            sugar_diff = sugar_limit - sugar
            data["bar_chart"]['sugar'][0]["data"].append({"x": date, "y": sugar if sugar < sugar_limit else sugar_limit, "the_goal": sugar_limit})
            data["bar_chart"]['sugar'][1]["data"].append({"x": date, "y": abs(sugar_diff), "fillColor": colour_over if sugar_diff < 0 else colour_normal})
            calories, protein, carbohydrates, fats, sugar = 0, 0, 0, 0, 0

            # last entry only contains a -1 to tell it its the last record and not run this again
        if entry[0] != -1:
            date = entry[0]
            calories += round(entry[1])
            protein += round(entry[2])
            carbohydrates += round(entry[3])
            fats += round(entry[4])
            sugar += round(entry[5])

            total_calories += round(entry[1])
            total_protein += round(entry[2])
            total_carbohydrates += round(entry[3])
            total_fats += round(entry[4])
            total_sugar += round(entry[5])
        
    data["month_calories"] = round(total_calories/(days/30))
    data["month_protein"] = round(total_protein/(days/30))
    data["month_carbohydrates"] = round(total_carbohydrates/(days/30))
    data["month_fats"] = round(total_fats/(days/30))
    data["month_sugar"] = round(total_sugar/(days/30))
    data["week_calories"] = round(total_calories/(days/7))
    data["week_protein"] = round(total_protein/(days/7))
    data["week_carbohydrates"] = round(total_carbohydrates/(days/7))
    data["week_fats"] = round(total_fats/(days/7))
    data["week_sugar"] = round(total_sugar/(days/7))
    data["day_calories"] = round(total_calories/days)
    data["day_protein"] = round(total_protein/days)
    data["day_carbohydrates"] = round(total_carbohydrates/days)
    data["day_fats"] = round(total_fats/days)
    data["day_sugar"] = round(total_sugar/days)
    data["start_date"] = start_date.strftime('%d/%m/%Y')
    data["end_date"] = end_date.strftime('%d/%m/%Y')
        
    nutrients_total = total_protein + total_carbohydrates + total_fats + total_sugar
    data["protein_percent"] = round(total_protein/nutrients_total * 100)
    data["carbohydrates_percent"] = round(total_carbohydrates/nutrients_total * 100)
    data["fats_percent"] = round(total_fats/nutrients_total * 100)
    data["sugar_percent"] = round(total_sugar/nutrients_total * 100)
    return data

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return render_template("logout.html")

if __name__ == '__main__':
    # Run the application using 'flask run'
    app.run(host="127.0.0.1", port=5000, debug=True)