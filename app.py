from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from jose import jwt, jwk,JWSError
from jose.utils import base64url_decode
from jose.exceptions import JWTError
import requests
import secrets
import time
from dotenv import load_dotenv
import os


load_dotenv()

def create_app():
    app = Flask(__name__, template_folder='templates')
    CORS(app, supports_credentials=True)
    app.secret_key = secrets.token_hex(32)

    client = MongoClient(os.getenv("MONGODB_URI"))
    app.db = client.Astrologi
    users_collection = app.db.users

    AUTH0_DOMAIN = 'dev-whbba5qnfveb88fc.us.auth0.com'
    ALGORITHMS = ['RS256']


    # Глобальный кэш для JWKS
    jwks_cache = None
    jwks_cache_time = None
    jwks_cache_ttl = 3600  # Время жизни кэша в секундах (например, 1 час)

    def get_jwks():
        global jwks_cache, jwks_cache_time
        now = time.time()

        # Возвращаем кэшированное значение, если оно еще действительно
        if jwks_cache and jwks_cache_time and now - jwks_cache_time < jwks_cache_ttl:
            return jwks_cache

        # Загружаем JWKS от Auth0, если кэш устарел или отсутствует
        try:
            jwks_url = f'https://{AUTH0_DOMAIN}/.well-known/jwks.json'
            response = requests.get(jwks_url)
            response.raise_for_status()
            jwks_cache = response.json()
            jwks_cache_time = now
            print(jwks_cache)
            return jwks_cache
        except requests.RequestException as e:
            raise Exception(f"Failed to retrieve JWKS: {e}")

    # Функция для проверки действительности idTokenHash
    @app.route('/test', methods=["POST"])
    def verify_auth0_token():
        data = request.json
        id_token_hash = data.get('id_token_hash')
        accessToken = data.get('accessToken')

        rsa_key = get_jwks()

        try:
            # Верификация токена
            payload = jwt.decode(
                id_token_hash,
                rsa_key,
                algorithms=ALGORITHMS,
                audience='ab7q8GJ0KvwbL0zAC6UwwLaQcXjgbUGT',
                issuer=f'https://{AUTH0_DOMAIN}/',
                access_token=accessToken
            )

            # Проверки после верификации
            if payload['email_verified']:
                # Поиск пользователя по email
                existing_user = users_collection.find_one({"email": payload['email']})

                formatted_time = datetime.utcnow().strftime("%d-%m-%Y %H:%M:%S")
                if not existing_user:
                    # Добавление нового пользователя в базу данных
                    users_collection.insert_one({
                        "email": payload['email'],
                        "user_info": payload,  # Или любые другие данные, которые вы хотите сохранить
                        "last_login": formatted_time,
                        "creat_now": formatted_time,
                    })
                    return jsonify({"success": True, "message": "New user added"}), 201
                else:
                    users_collection.update_one(
                        {"email": payload['email']},
                        {"$set": {"last_login": formatted_time}}
                    )
                    # Пользователь уже существует
                    return jsonify({"success": True, "message": "User already exists"}), 200
            else:
                return jsonify({"success": False, "error": "Email not verified"}), 400

        except JWTError as e:
            return jsonify({"success": False, "error": str(e)}), 400
        


    @app.route('/', methods=["GET"])
    def home():
        return render_template('index.html')


    @app.route('/<path:path>', methods=["GET"])
    def catch_all(path):
        return render_template('index.html')


    #Добавление даты рождения
    @app.route('/update_user_info', methods=["POST"])
    def update_user_info():
        data = request.json
        id_token_hash = data.get('idTokenHash')
        accessToken = data.get('accessToken')
        print(f"Received token: {id_token_hash}")

        try:
            rsa_key = get_jwks()

            # Верификация токена
            payload = jwt.decode(
                id_token_hash,
                rsa_key,
                algorithms=ALGORITHMS,
                audience='ab7q8GJ0KvwbL0zAC6UwwLaQcXjgbUGT',
                issuer=f'https://{AUTH0_DOMAIN}/',
                access_token=accessToken
            )
            print("Token successfully decoded")
            # Обновляем информацию пользователя
            email = payload['email']
            birth_date = data['birthDate']
            birth_date_obj = datetime.strptime(birth_date, '%Y-%m-%d')
            birth_date_formatted = birth_date_obj.strftime('%d.%m.%Y')
            born_at_night = data['bornAtNight']

            users_collection.update_one(
                {"email": email},
                {"$set": {
                    "birth_date": birth_date_formatted,
                    "born_at_night": born_at_night == 'yes'
                }}
            )
            print("User info updated")
            return jsonify({"success": True, "message": "User info updated"}), 200

        except (JWSError, Exception) as e:  # Обработка ошибок JWT и других потенциальных ошибок
            print(f"Error during token processing: {e}")
            return jsonify({"success": False, "error": str(e)}), 400
        

    # РАЗДЕЛ Все о личном

    # Характер и сознание
    @app.route('/getCharacterInfo', methods=["POST"])
    def get_character_info():
        data = request.json
        id_token = data.get('idToken')
        accessToken = data.get('accessToken')

        rsa_key = get_jwks()

        # Верификация токена и извлечение email пользователя
        try:
            payload = jwt.decode(id_token, rsa_key, algorithms=ALGORITHMS, audience='ab7q8GJ0KvwbL0zAC6UwwLaQcXjgbUGT', issuer=f'https://{AUTH0_DOMAIN}/',access_token=accessToken)
            email = payload['email']
        except JWTError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        # Поиск пользователя в базе данных
        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        birth_date = user.get('birth_date')
        born_at_night = user.get('born_at_night', False)

        # Логика определения номера файла
        day_of_birth = int(birth_date.split('.')[0])  # Предполагаем, что birth_date в формате 'DD.MM.YYYY'
        file_number = day_of_birth - 1 if born_at_night else day_of_birth

        print(f"твоя поебота{file_number}")
        try:
            # Чтение содержимого файла
            file_path = f'static/files/HaracterAndSosnanie/{file_number}.txt'  # Путь к файлу
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.read()
        except FileNotFoundError:
            return jsonify({"success": False, "error": "File not found"}), 404

        # Возвращаем содержимое файла вместо номера
        return jsonify({"success": True, "message": "Character info fetched", "fileContent": file_content}), 200


    #Способность и миссии
    @app.route('/SposobnoctiAndMission', methods=["POST"])
    def life_approaches_and_methods():
        data = request.json
        id_token = data.get('idToken')
        accessToken = data.get('accessToken')

        rsa_key = get_jwks()

        # Верификация токена и извлечение email пользователя
        try:
            payload = jwt.decode(id_token, rsa_key, algorithms=ALGORITHMS, audience='ab7q8GJ0KvwbL0zAC6UwwLaQcXjgbUGT', issuer=f'https://{AUTH0_DOMAIN}/',access_token=accessToken)
            email = payload['email']
        except JWTError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        # Поиск пользователя в базе данных
        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        birth_date = user.get('birth_date')
        born_at_night = user.get('born_at_night', False)
        day_of_birth, month_of_birth = map(int, birth_date.split('.')[0:2])

        # Рассчитываем номер файла
        file_number = (sum(map(int, str(day_of_birth))) + sum(map(int, str(month_of_birth))) - (1 if born_at_night else 0)) % 9 or 9
        print(file_number)
        try:
            # Чтение содержимого файла
            file_path = f'static/files/SposobnostiAndMission/{file_number}.txt'  # Путь к файлу
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.read()
        except FileNotFoundError:
            return jsonify({"success": False, "error": "File not found"}), 404

        # Возвращаем содержимое файла
        return jsonify({"success": True, "message": "Life approaches and methods info fetched", "fileContent": file_content}), 200


    #Условия и задачи для самореализации
    @app.route('/selfRealizationConditions', methods=["POST"])
    def self_realization_conditions():
        data = request.json
        id_token = data.get('idToken')
        accessToken = data.get('accessToken')

        rsa_key = get_jwks()

        try:
            payload = jwt.decode(id_token, rsa_key, algorithms=ALGORITHMS, audience='ab7q8GJ0KvwbL0zAC6UwwLaQcXjgbUGT', issuer=f'https://{AUTH0_DOMAIN}/',access_token=accessToken)
            email = payload['email']
        except JWTError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        birth_date = user.get('birth_date')
        born_at_night = user.get('born_at_night', False)

        # Разбор даты рождения и вычисление
        day, month, year = map(int, birth_date.split('.'))
        result = sum(map(int, str(day))) + sum(map(int, str(month))) + sum(map(int, str(year))) - (1 if born_at_night else 0)
        result = result % 9 or 9  # Приведение к однозначному числу

        try:
            file_path = f'static/files/RealizationConditions/{result}.txt'
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.read()
        except FileNotFoundError:
            return jsonify({"success": False, "error": "File not found"}), 404

        return jsonify({"success": True, "message": "Self-realization conditions info fetched", "fileContent": file_content}), 200


    #Рекомендации и предостережения
    @app.route('/recommendationsAndWarnings', methods=["POST"])
    def recommendations_and_warnings():
        data = request.json
        id_token = data.get('idToken')
        accessToken = data.get('accessToken')

        rsa_key = get_jwks()

        try:
            payload = jwt.decode(id_token, rsa_key, algorithms=ALGORITHMS, audience='ab7q8GJ0KvwbL0zAC6UwwLaQcXjgbUGT', issuer=f'https://{AUTH0_DOMAIN}/',access_token=accessToken)
            email = payload['email']
        except JWTError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        born_at_night = user.get('born_at_night', False)
        birth_date = user.get('birth_date')
        day_of_birth = int(birth_date.split('.')[0])

        if born_at_night:
            file_number = (sum(map(int, str(day_of_birth - 1))) % 9) or 9
        else:
            file_number = (sum(map(int, str(day_of_birth))) % 9) or 9

        try:
            file_path = f'static/files/RecommendationsAndWarnings/{file_number}.txt'
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.read()
        except FileNotFoundError:
            return jsonify({"success": False, "error": "File not found"}), 404

        return jsonify({"success": True, "message": "Recommendations and warnings info fetched", "fileContent": file_content}), 200



    def to_single_digit(number):
        """Функция для приведения числа к однозначному путем суммирования его цифр."""
        while number > 9:
            number = sum(map(int, str(number)))
        return number



    #Главная проблема
    @app.route('/mainProblem', methods=["POST"])
    def main_problem():
        data = request.json
        id_token = data.get('idToken')
        accessToken = data.get('accessToken')

        rsa_key = get_jwks()

        try:
            payload = jwt.decode(id_token, rsa_key, algorithms=ALGORITHMS, audience='ab7q8GJ0KvwbL0zAC6UwwLaQcXjgbUGT', issuer=f'https://{AUTH0_DOMAIN}/',access_token=accessToken)
            email = payload['email']
        except JWTError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        born_at_night = user.get('born_at_night', False)
        birth_date = user.get('birth_date')
        day, month, year = map(int, birth_date.split('.'))

        day_digit = to_single_digit(day - 1 if born_at_night else day)
        month_digit = to_single_digit(month)
        year_digit = to_single_digit(year)

        # Этапы вычисления
        step1_result = abs(day_digit - month_digit)
        step2_result = abs(day_digit - year_digit)
        final_result = to_single_digit(step1_result - step2_result)

        try:
            file_path = f'static/files/MainProblem/{final_result}.txt'
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.read()
        except FileNotFoundError:
            return jsonify({"success": False, "error": "File not found"}), 404

        return jsonify({"success": True, "message": "Main problem info fetched", "fileContent": file_content}), 200



    #Здоровье
    @app.route('/healthInfo', methods=["POST"])
    def health_info():
        data = request.json
        id_token = data.get('idToken')
        accessToken = data.get('accessToken')

        rsa_key = get_jwks()

        try:
            payload = jwt.decode(id_token, rsa_key, algorithms=ALGORITHMS, audience='ab7q8GJ0KvwbL0zAC6UwwLaQcXjgbUGT', issuer=f'https://{AUTH0_DOMAIN}/',access_token=accessToken)
            email = payload['email']
        except JWTError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        born_at_night = user.get('born_at_night', False)
        birth_date = user.get('birth_date')
        day = int(birth_date.split('.')[0])

        file_number = sum(map(int, str(day - 1 if born_at_night else day))) % 9 or 9
        print(file_number)
        try:
            file_path = f'static/files/HealthInfo/{file_number}.txt'
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.read()
        except FileNotFoundError:
            return jsonify({"success": False, "error": "File not found"}), 404

        return jsonify({"success": True, "message": "Health info fetched", "fileContent": file_content}), 200



    #Профессия
    @app.route('/professionInfo', methods=["POST"])
    def profession_info():
        data = request.json
        id_token = data.get('idToken')
        accessToken = data.get('accessToken')

        rsa_key = get_jwks()

        try:
            payload = jwt.decode(id_token, rsa_key, algorithms=ALGORITHMS, audience='ab7q8GJ0KvwbL0zAC6UwwLaQcXjgbUGT', issuer=f'https://{AUTH0_DOMAIN}/',access_token=accessToken)
            email = payload['email']
        except JWTError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        born_at_night = user.get('born_at_night', False)
        birth_date = user.get('birth_date')
        day = int(birth_date.split('.')[0])

        file_number = sum(map(int, str(day - 1 if born_at_night else day))) % 9 or 9

        try:
            file_path = f'static/files/Profesion/{file_number}.txt'
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.read()
        except FileNotFoundError:
            return jsonify({"success": False, "error": "File not found"}), 404

        return jsonify({"success": True, "message": "Profession info fetched", "fileContent": file_content}), 200



    #Подходы и методы в жизни
    @app.route('/approachesAndMethods', methods=["POST"])
    def approaches_and_methods():
        data = request.json
        id_token = data.get('idToken')
        accessToken = data.get('accessToken')

        rsa_key = get_jwks()

        try:
            payload = jwt.decode(id_token, rsa_key, algorithms=ALGORITHMS, audience='ab7q8GJ0KvwbL0zAC6UwwLaQcXjgbUGT', issuer=f'https://{AUTH0_DOMAIN}/',access_token=accessToken)
            email = payload['email']
        except JWTError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        birth_date = user.get('birth_date')
        month, year = birth_date.split('.')[1:3]

        # Преобразование месяца и года к однозначным числам
        month_digit = sum(map(int, month)) % 9 or 9
        year_digits = sum(map(int, year)) % 9 or 9

        try:
            approaches_file_path = f'static/files/Podhosi/{month_digit}.txt'
            methods_file_path = f'static/files/Methods/{year_digits}.txt'

            # Чтение и объединение содержимого двух файлов
            with open(approaches_file_path, 'r', encoding='utf-8') as approaches_file, open(methods_file_path, 'r', encoding='utf-8') as methods_file:
                file_content = approaches_file.read() + "\n\n" + methods_file.read()

        except FileNotFoundError:
            return jsonify({"success": False, "error": "File not found"}), 404

        return jsonify({
            "success": True,
            "message": "Approaches and methods info fetched",
            "fileContent": file_content
        }), 200



    #Детская нумерология
    #Характе, сильные и слабые стороны
    @app.route('/characterTraits', methods=["POST"])
    def character_traits():
        data = request.json
        id_token = data.get('idToken')
        accessToken = data.get('accessToken')

        rsa_key = get_jwks()

        try:
            payload = jwt.decode(id_token, rsa_key, algorithms=ALGORITHMS, audience='ab7q8GJ0KvwbL0zAC6UwwLaQcXjgbUGT', issuer=f'https://{AUTH0_DOMAIN}/',access_token=accessToken)
            email = payload['email']
        except JWTError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        born_at_night = user.get('born_at_night', False)
        birth_date = user.get('birth_date')
        day = int(birth_date.split('.')[0])
        file_number = (sum(map(int, str(day))) - 1 if born_at_night else sum(map(int, str(day)))) % 9 or 9

        try:
            file_path = f'static/files/XaracretSilnuiSkabiuStoroni/{file_number}.txt'
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.read()
        except FileNotFoundError:
            return jsonify({"success": False, "error": "File not found"}), 404

        return jsonify({
            "success": True,
            "message": "Character traits info fetched",
            "fileContent": file_content
        }), 200


    #рекомендации по воспитанию
    @app.route('/educationRecommendations', methods=["POST"])
    def education_recommendations():
        data = request.json
        id_token = data.get('idToken')
        accessToken = data.get('accessToken')

        rsa_key = get_jwks()

        try:
            payload = jwt.decode(id_token, rsa_key, algorithms=ALGORITHMS, audience='ab7q8GJ0KvwbL0zAC6UwwLaQcXjgbUGT', issuer=f'https://{AUTH0_DOMAIN}/',access_token=accessToken)
            email = payload['email']
        except JWTError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        born_at_night = user.get('born_at_night', False)
        birth_date = user.get('birth_date')
        day = int(birth_date.split('.')[0])

        file_number = (sum(map(int, str(day))) - 1) % 9 or 9 if born_at_night else sum(map(int, str(day))) % 9 or 9

        try:
            file_path = f'static/files/EducationRecommendations/{file_number}.txt'
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.read()
        except FileNotFoundError:
            return jsonify({"success": False, "error": "File not found"}), 404

        return jsonify({"success": True, "message": "Education recommendations info fetched", "fileContent": file_content}), 200



    #Профессия
    @app.route('/professionInfoKids', methods=["POST"])
    def profession_info_kids():
        data = request.json
        id_token = data.get('idToken')
        accessToken = data.get('accessToken')

        rsa_key = get_jwks()

        try:
            payload = jwt.decode(id_token, rsa_key, algorithms=ALGORITHMS, audience='ab7q8GJ0KvwbL0zAC6UwwLaQcXjgbUGT', issuer=f'https://{AUTH0_DOMAIN}/',access_token=accessToken)
            email = payload['email']
        except JWTError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        born_at_night = user.get('born_at_night', False)
        birth_date = user.get('birth_date')
        day, month, year = map(int, birth_date.split('.'))

        result = sum(map(int, str(day) + str(month) + str(year))) - 1 if born_at_night else sum(map(int, str(day) + str(month) + str(year)))
        result = sum(map(int, str(result)))  # Приводим к однозначному числу

        try:
            file_path = f'static/files/ProfessionsKids/{result}.txt'
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.read()
        except FileNotFoundError:
            return jsonify({"success": False, "error": "File not found"}), 404

        return jsonify({"success": True, "message": "Profession info fetched", "fileContent": file_content}), 200



    #Солярный год
    @app.route('/solarYearInfo', methods=["POST"])
    def solar_year_info():
        data = request.json
        id_token = data.get('idToken')
        accessToken = data.get('accessToken')
        interested_year = data.get('interestedYear')

        rsa_key = get_jwks()

        try:
            payload = jwt.decode(id_token, rsa_key, algorithms=ALGORITHMS, audience='ab7q8GJ0KvwbL0zAC6UwwLaQcXjgbUGT', issuer=f'https://{AUTH0_DOMAIN}/',access_token=accessToken)
            email = payload['email']
        except JWTError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        born_at_night = user.get('born_at_night')
        birth_date = user.get('birth_date')
        day, month, year = map(int, birth_date.split('.'))

        total = sum(map(int, str(day) + str(month) + str(year) + str(interested_year))) - 1 if born_at_night else sum(map(int, str(day) + str(month) + str(year) + str(interested_year)))
        #result = total % 11  # Поскольку в папке 11 файлов
        result = total % 9

        try:
            file_path = f'static/files/SolarYear/{result}.txt'
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.read()
        except FileNotFoundError:
            return jsonify({"success": False, "error": "File not found"}), 404

        return jsonify({"success": True, "message": "Solar year info fetched", "fileContent": file_content}), 200




    #Совместимость
    #Партнер 1!!!!!!!!!!!!!!!!!!!!
    @app.route('/partner1Info', methods=["POST"])
    def partner1_info():
        data = request.json
        id_token = data.get('idToken')
        accessToken = data.get('accessToken')

        rsa_key = get_jwks()

        try:
            payload = jwt.decode(id_token, rsa_key, algorithms=ALGORITHMS, audience='ab7q8GJ0KvwbL0zAC6UwwLaQcXjgbUGT', issuer=f'https://{AUTH0_DOMAIN}/',access_token=accessToken)
            email = payload['email']
        except JWTError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        born_at_night = user.get('born_at_night', False)
        birth_date = user.get('birth_date')
        day = int(birth_date.split('.')[0])

        result = (sum(map(int, str(day))) - 1 if born_at_night else sum(map(int, str(day)))) % 9 or 9

        try:
            file_path = f'static/files/Partner1/{result}.txt'
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.read()
        except FileNotFoundError:
            return jsonify({"success": False, "error": "File not found"}), 404

        return jsonify({"success": True, "message": "Partner 1 info fetched", "fileContent": file_content}), 200


    #Партнер 2
    @app.route('/partner2Info', methods=["POST"])
    def partner2_info():
        data = request.json
        id_token = data.get('idToken')
        accessToken = data.get('accessToken')

        rsa_key = get_jwks()

        try:
            payload = jwt.decode(id_token, rsa_key, algorithms=ALGORITHMS, audience='ab7q8GJ0KvwbL0zAC6UwwLaQcXjgbUGT', issuer=f'https://{AUTH0_DOMAIN}/',access_token=accessToken)
            email = payload['email']
        except JWTError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        born_at_night = data.get('partnerBornAtNight')
        partner2_birth_date = data.get('partnerBirthDate')  # Убедитесь, что у вас есть такое поле
        day = int(partner2_birth_date.split('-')[0])

        result = (sum(map(int, str(day))) - 1 if born_at_night else sum(map(int, str(day)))) % 9 or 9

        try:
            file_path = f'static/files/Partner2/{result}.txt'
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.read()
        except FileNotFoundError:
            return jsonify({"success": False, "error": "File not found"}), 404

        return jsonify({"success": True, "message": "Partner 2 info fetched", "fileContent": file_content}), 200


    #Сщвместимость
    @app.route('/compatibility', methods=["POST"])
    def compatibility():
        data = request.json
        id_token = data.get('idToken')
        accessToken = data.get('accessToken')
        partner2_birth_date = data.get('partnerBirthDate')
        partner2_born_at_night = data.get('partnerBornAtNight', False)
        print(partner2_birth_date,partner2_born_at_night)

        rsa_key = get_jwks()

        try:
            payload = jwt.decode(id_token, rsa_key, algorithms=ALGORITHMS, audience='ab7q8GJ0KvwbL0zAC6UwwLaQcXjgbUGT', issuer=f'https://{AUTH0_DOMAIN}/',access_token=accessToken)
            email = payload['email']
        except JWTError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        # Извлечение информации о пользователе (партнер 1) из базы данных
        user = users_collection.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        partner1_born_at_night = user.get('born_at_night', False)
        partner1_birth_date = user.get('birth_date')
        
        # Вычисление номеров для партнеров
        partner1_number = int(partner1_birth_date.split('.')[0]) - (1 if partner1_born_at_night else 0)
        partner2_number = int(partner2_birth_date.split('-')[2]) - (1 if partner2_born_at_night else 0)

        file_name = partner1_number + partner2_number
        print(file_name)
        try:
            file_path = f'static/files/Compatibility/{file_name}.txt'
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.read()
        except FileNotFoundError:
            return jsonify({"success": False, "error": f"Compatibility file {file_name} not found"}), 404

        return jsonify({"success": True, "fileContent": file_content}), 200


    if __name__ == "__main__":
        app.run(debug=True)

    
    return app