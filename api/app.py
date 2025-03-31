import concurrent.futures
from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from dotenv import load_dotenv
import re
import helpers.sql_helper as sql_helper
from helpers.azure_ai_helper import get_azure_ai_response_from_conversation

# Load environment variables from .env file
load_dotenv()
client_url = os.getenv('CLIENT_URL')
allowed_daily_chats = int(os.getenv('ALLOWED_DAILY_CHATS'))

app = Flask(__name__)

# Set CORS configuration
CORS(app, resources={r"/*": {"origins": client_url}})

def generate_bot_id(bot_name):
    """Generate a botId based on bot name."""
    bot_name = bot_name.strip()
    bot_id = bot_name.replace(" ", "-")
    bot_id = re.sub(r'[^a-zA-Z0-9-]', '', bot_id)
    bot_id = bot_id.lower()
    return bot_id

@app.route('/is-db-active', methods=['GET'])
def is_db_active():
    """Checks if the 'Bots' database is active (ONLINE) with a timeout of 4 seconds."""
    
    def check_database_status():
        with sql_helper.get_conn() as conn:
            status = sql_helper.get_database_status(conn)
            if status is None:
                return {"isActive": False}
            return {"isActive": status.get("status") == "ONLINE"}
    
    try:
        # Execute the task with a timeout using concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(check_database_status)
            return jsonify(future.result(timeout=2.5)), 200

    except concurrent.futures.TimeoutError:
        return jsonify({"isActive": False}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Route for chatting with a bot
@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    conversation = data.get('messages')
    bot_details = data.get('botDetails')
    only_answer_with_context = bot_details.get('onlyAnswerWithContext')
    user = data.get('user')

    with sql_helper.get_conn() as sql_connection:
        todays_count = sql_helper.get_todays_count(sql_connection, user)
        if todays_count > allowed_daily_chats:
            return jsonify({'message': 'Sorry, usage of chatbots has reached its limit for the day'})
        sql_helper.increment_today_count(sql_connection, user)

    if isinstance(only_answer_with_context, str):
        only_answer_with_context = only_answer_with_context.lower() == 'true'
    
    message = get_azure_ai_response_from_conversation(conversation, bot_details['responseStyle'], bot_details['context'], only_answer_with_context)

    if message:
        return jsonify({'message': message})
    else:
        return jsonify({'message': 'There was an error getting a response from the bot. Please try again later.'}), 500

@app.route('/get_bots', methods=['POST'])
def get_bots_endpoint():
    data = request.json
    filters = data.get('filter', {})  # Optional filter object

    with sql_helper.get_conn() as conn:
        try:
            # Call the helper function to get bots with the provided filters
            bots = sql_helper.get_bots(conn, filters)
            if bots is None:
                return jsonify({"error": "Failed to fetch bots"}), 500

            return jsonify(bots), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/create_bot', methods=['POST'])
def create_bot_endpoint():
    data = request.json
    bot = data.get('bot')

    # Extract required and optional fields from the payload
    description = bot.get('description')
    name = bot['name']
    context = bot['context']
    user_id = data.get('userId')
    is_featured = bot.get('isFeatured', 0)
    greeting_text = bot.get('greetingText')
    only_answer_with_context = bot.get('onlyAnswerWithContext', 0)
    response_style = bot.get('responseStyle')

    # Generate the botId
    bot_id = generate_bot_id(name)

    with sql_helper.get_conn() as conn:
        try:
            # Create the bot with the new attributes
            result, message = sql_helper.create_bot(
                conn, name, bot_id, user_id, description, context, is_featured, greeting_text,
                only_answer_with_context, response_style
            )
            if not result:
                return jsonify({"error": message}), 500

            return jsonify({
                "message": f"Bot '{name}' created successfully",
                "id": bot_id
            }), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/update_bot', methods=['PUT'])
def update_bot_endpoint():
    data = request.json
    old_bot = data.get('oldBot')
    new_bot = data.get('newBot')

    with sql_helper.get_conn() as conn:
        try:
            # Generate a new bot ID if the name has changed
            old_bot_id = old_bot['id']
            new_bot_id = old_bot_id
            if old_bot['name'] != new_bot['name']:
                new_bot_id = generate_bot_id(new_bot['name'])

            # Call the update helper function
            result, message = sql_helper.update_bot(
                conn,
                old_bot_id=old_bot_id,
                new_bot_id=new_bot_id,
                new_name=new_bot['name'],
                new_description=new_bot.get('description'),
                new_context=new_bot.get('context'),
                is_featured=new_bot.get('isFeatured', 0),
                greeting_text=new_bot.get('greetingText'),
                only_answer_with_context=new_bot.get('onlyAnswerWithContext', 0),
                response_style=new_bot.get('responseStyle')
            )

            if result:
                return jsonify({"message": "Bot updated successfully", "botId": new_bot_id}), 200
            else:
                return jsonify({"error": message}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/delete_bot/<bot_id>', methods=['DELETE'])
def delete_bot_endpoint(bot_id):
    with sql_helper.get_conn() as conn:
        try:
            result = sql_helper.delete_bot(conn, bot_id)
            if result:
                return jsonify({"message": f"Bot '{bot_id}' deleted successfully"}), 200
            else:
                return jsonify({"error": f"Bot '{bot_id}' not found or could not be deleted"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

# Define the ping endpoint
@app.route('/')
def ping():
    return "Ping successful!", 200

# Start the Flask server
if __name__ == '__main__':
    local_dev = False
    if local_dev:
        port = int(os.getenv('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=True)
    else:
        app.run()