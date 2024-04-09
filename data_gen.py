import random, datetime, sqlite3

def generate_data(user_id):
    today = datetime.datetime.now().date()
    two_months_ago = today - datetime.timedelta(days=124)
    conn = sqlite3.connect('db.sqlite3')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM food")
    food_data = cursor.fetchall()
    
    for i in range(124):
        meals = random.randint(4, 8)
        date = two_months_ago + datetime.timedelta(days=i)
        for j in range(meals):
            food_details = random.choice(food_data)
            if j <= 2: meal_type = "breakfast"
            elif j > 2 and j <= 4: meal_type = "lunch"
            elif j > 4 and j <= 6: meal_type = "dinner"
            else: meal_type = "snack"
            food_id = food_details[2]
            protein = food_details[4]
            carbohydrates = food_details[3]
            fats = food_details[6]
            sugar = food_details[5]
            calories = protein * 4 + carbohydrates * 4 + fats * 9 + sugar * 4
        
            cursor.execute("""
                INSERT INTO UserIntake (UserID, FoodID, MealType, Date, DailyCalories, DailyProtein,
                                        DailyCarbohydrates, DailyFats, DailySugar)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, food_id, meal_type, date, calories, protein, carbohydrates, fats, sugar))
            conn.commit()
    conn.close()
    
generate_data(user_id=8)