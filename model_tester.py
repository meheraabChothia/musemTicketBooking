import os
import openai
import time
from datetime import datetime, timedelta

# Initialize OpenAI client with SambaNova API
client = openai.OpenAI(
    api_key="100cfa62-287e-4983-8986-010da6320a53",
    base_url="https://api.sambanova.ai/v1",
)

# Available models
MODELS = [
    "Meta-Llama-3.1-70B-Instruct",  # Original model from history_samba_continuous_function.py
    "Meta-Llama-3.2-3B-Instruct",     
    "Meta-Llama-3.3-70B-Instruct"     
]

def get_current_date():
    """Returns the current date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")

# Get today's date to supply to the chatbot
current_date = get_current_date()

INITIAL_CONVERSATION_HISTORY = [{
    "role": "system",
    "content": f"""
You are an AI-powered chatbot for an online museum ticketing system.

Your tasks:
1. Booking tickets
2. Updating existing bookings
3. Deleting bookings
4. Engaging in general conversation

### IMPORTANT RULES:
1. **Always identify the user's intent first** before generating a response.
2. **Always return responses in a valid JSON format**. No exceptions.
3. **Never miss asking for missing information**. If any field is `null`, prompt the user to provide it.

### RESTRICTIONS:
- Do **not** mention reference numbers.
- Do **not** provide ticket prices or costs in responses.
- Do **not** tell the user that their details have been sent via phone or email.

### FAQs:
- **Ticket Prices**:
  - Adult (18+): 50
  - Child (Under 18): 25
- **Museum Timings**:
  - Open from **10:00 AM to 6:00 PM**.
  - **Closed on Mondays**.

### Response format:
#### For booking a ticket:
{{
  "response": "<Reply to the user>",
  "task": "<One of: 'booking_ticket', 'updating_booking', 'deleting_booking', 'general_chat'>",
  "entities": {{
    "name": "<Extracted name or null>",
    "phone_number": "<Extracted phone number or null>",
    "email": "<Extracted email address or null>",
    "children_tickets": "<Number of child tickets (under 18) or null>",
    "adult_tickets": "<Number of adult tickets (18+) or null>",
    "date": "<Extracted date in YYYY-MM-DD format or null>",
    "time": "<Extracted time in HH:MM format or null>"
  }}
}}

#### For updating a ticket:
{{
  "response": "<Reply to the user>",
  "task": "<One of: 'booking_ticket', 'updating_booking', 'deleting_booking', 'general_chat'>",
  "entities": {{
    "phone_number": "<Extracted phone number or null>",
    "date": "<Extracted date in YYYY-MM-DD format or null>",
    "time": "<Extracted time in HH:MM format or null>"
  }}
}}

#### For deleting a ticket:
{{
  "response": "<Reply to the user>",
  "task": "<One of: 'booking_ticket', 'updating_booking', 'deleting_booking', 'general_chat'>",
  "entities": {{
    "phone_number": "<Extracted phone number or null>"
  }}
}}

### Rules for Processing:
1. **Intent Classification**: Identify the user's request and classify it as one of the four tasks.
2. **Entity Extraction**: Extract the required details based on the identified intent.
3. **Ticket Categorization**:
   - Always separate tickets into `children_tickets` (under 18) and `adult_tickets` (18+).
   - If the user gives a total number of tickets without specifying, ask how many are for children and how many are for adults.
4. **Date Handling**:
   - Use `YYYY-MM-DD` format.
   - Today's date is `{current_date}`.
   - If the user provides a weekday (e.g., "Saturday"), return the next occurrence of that day relative to `{current_date}`.
   - If the user says "tomorrow," return `{current_date} + 1 day`.
   - **Do not allow bookings for Mondays.** If the user selects a Monday, inform them and ask for another date.
5. **Time Handling**:
   - Convert times into `HH:MM` (24-hour format).
   - Examples: "3 AM" → "03:00", "2 PM" → "14:00", "07:45 PM" → "19:45".
   - **Only allow bookings between 10:00 and 18:00 (6 PM).** If the user selects an invalid time, inform them and ask for a valid time.
6. **Updating a Booking**:
   - If the intent is `updating_booking`, ask the user for their `phone_number`.
   - Also, request `date` and `time` for the updated booking.
   - If `date` and `time` are missing, set them as `null` and prompt the user to provide them.
7. **Deleting a Booking**:
   - If the intent is `deleting_booking`, only ask for the `phone_number`.
   - No need to collect additional details for deletion.
8. **Missing Fields**:
   - If any required entity is `null`, always prompt the user to provide it.
"""
}]


def generate_response(model_name, user_message, conversation_history):
    """
    Generate a response from a specific model.
    
    Args:
        model_name (str): The name of the model to use
        user_message (str): User's message
        conversation_history (list): Conversation history in the required format
        
    Returns:
        tuple: (response text, updated conversation history)
    """
    # Create a copy of the conversation history to avoid modifying the original
    history_copy = conversation_history.copy()
    
    # Add user message to history
    user_dict = {"role": "user", "content": user_message}
    history_copy.append(user_dict)
    
    # Get response from the model
    response = client.chat.completions.create(
        model=model_name,
        messages=history_copy,
        temperature=0.1,
        top_p=0.1,
    )
    
    response_text = response.choices[0].message.content
    
    # Add assistant response to history
    assistant_dict = {"role": "assistant", "content": response_text}
    history_copy.append(assistant_dict)
    
    return response_text, history_copy

def test_models(user_input, system_prompt=None):
    """
    Test all models with the same input and return their responses.
    
    Args:
        user_input (str): The user's input message
        system_prompt (str, optional): System prompt to use
        
    Returns:
        dict: Dictionary mapping model names to their responses
    """
    results = {}
    
    # Initialize conversation history with INITIAL_CONVERSATION_HISTORY
    conversation_history = INITIAL_CONVERSATION_HISTORY.copy()
    
    # If system prompt is provided, replace the existing system prompt
    if system_prompt:
        # Replace the system message if it exists
        for i, message in enumerate(conversation_history):
            if message["role"] == "system":
                conversation_history[i] = {"role": "system", "content": system_prompt}
                break
        else:
            # If no system message found, add one
            conversation_history.insert(0, {"role": "system", "content": system_prompt})
    
    # Test each model with a delay between models
    for i, model in enumerate(MODELS):
        print(f"Testing model: {model}...")
        response, _ = generate_response(model, user_input, conversation_history)
        results[model] = response
        
        # Add delay between models (except after the last one)
        if i < len(MODELS) - 1:
            print(f"Waiting 10 seconds before testing next model...")
            time.sleep(10)
    
    return results

def format_results(user_input, results):
    """
    Format the results for display and saving.
    
    Args:
        user_input (str): The user's input
        results (dict): Dictionary of model responses
        
    Returns:
        str: Formatted results
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    formatted = f"=== Model Comparison Results ({timestamp}) ===\n\n"
    formatted += f"USER INPUT:\n{user_input}\n\n"
    
    for model, response in results.items():
        formatted += f"MODEL: {model}\n"
        formatted += "=" * 80 + "\n"
        formatted += f"{response}\n\n"
        formatted += "=" * 80 + "\n\n"
    
    return formatted

def save_results(formatted_results):
    """
    Save the formatted results to results.txt
    
    Args:
        formatted_results (str): The formatted results to save
    """
    with open("results.txt", "a", encoding="utf-8") as f:
        f.write(formatted_results)
        f.write("\n\n" + "#" * 100 + "\n\n")  # Add separator between runs

def test_single_model(model_name, user_input):
    """
    Test a single model with the given input and return its response.
    
    Args:
        model_name (str): The name of the model to use
        user_input (str): The user's input message
        
    Returns:
        str: The model's response
    """
    # Initialize conversation history with INITIAL_CONVERSATION_HISTORY
    conversation_history = INITIAL_CONVERSATION_HISTORY.copy()
    
    print(f"Testing model: {model_name}...")
    response, _ = generate_response(model_name, user_input, conversation_history)
    return response

def format_single_model_results(user_input, model_name, response):
    """
    Format the results for a single model for display and saving.
    
    Args:
        user_input (str): The user's input
        model_name (str): The name of the model
        response (str): The model's response
        
    Returns:
        str: Formatted results
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    formatted = f"=== Single Model Test Results ({timestamp}) ===\n\n"
    formatted += f"MODEL: {model_name}\n"
    formatted += f"USER INPUT:\n{user_input}\n\n"
    formatted += "=" * 80 + "\n"
    formatted += f"{response}\n\n"
    formatted += "=" * 80 + "\n\n"
    
    return formatted

def main():
    print("=== Model Testing Utility ===")
    print(f"Available models: {', '.join(MODELS)}")
    
    while True:
        # Ask user for test mode
        test_mode = input("\nChoose test mode:\n1. Test all models\n2. Test a single model\n3. Exit\nEnter choice (1/2/3): ")
        
        if test_mode == "3" or test_mode.lower() == 'exit':
            print("Exiting...")
            break
            
        elif test_mode == "1":
            # Test all models
            input_method = input("\nChoose input method:\n1. Manual input\n2. From file (input.txt)\nEnter choice (1/2): ")
            
            if input_method == "1":
                # Manual input
                user_input = input("\nEnter your test input: ")
                if user_input.lower() == 'exit':
                    continue
                    
                # Test all models
                results = test_models(user_input)
                
                # Format and display results
                formatted_results = format_results(user_input, results)
                print("\n" + formatted_results)
                
                # Save results
                save_results(formatted_results)
                print("Results saved to results.txt")
                
            elif input_method == "2":
                # From file
                try:
                    with open("input.txt", "r", encoding="utf-8") as f:
                        inputs = f.read().splitlines()
                    
                    if not inputs:
                        print("Error: input.txt is empty. Please add some inputs to the file.")
                        continue
                        
                    print(f"Found {len(inputs)} inputs in input.txt")
                    
                    for i, user_input in enumerate(inputs):
                        if not user_input.strip():  # Skip empty lines
                            continue
                            
                        print(f"\nProcessing input {i+1}/{len(inputs)}: {user_input[:50]}...")
                        
                        # Test all models
                        results = test_models(user_input)
                        
                        # Format and display results
                        formatted_results = format_results(user_input, results)
                        print("\n" + formatted_results)
                        
                        # Save results
                        save_results(formatted_results)
                        print(f"Results for input {i+1} saved to results.txt")
                        
                        # Add delay between inputs (except after the last one)
                        if i < len(inputs) - 1:
                            print("Waiting 10 seconds before processing next input...")
                            time.sleep(10)
                    
                    print("All inputs from file processed successfully.")
                    
                except FileNotFoundError:
                    print("Error: input.txt not found. Please create this file with your inputs.")
            
        elif test_mode == "2":
            # Test a single model
            # Let user select which model to test
            print("\nAvailable models:")
            for i, model in enumerate(MODELS):
                print(f"{i+1}. {model}")
                
            model_choice = input("\nSelect model number: ")
            try:
                model_index = int(model_choice) - 1
                if model_index < 0 or model_index >= len(MODELS):
                    print(f"Invalid choice. Please enter a number between 1 and {len(MODELS)}.")
                    continue
                    
                selected_model = MODELS[model_index]
                print(f"Selected model: {selected_model}")
                
                # Choose input method
                input_method = input("\nChoose input method:\n1. Manual input\n2. From file (input.txt)\nEnter choice (1/2): ")
                
                if input_method == "1":
                    # Manual input
                    user_input = input("\nEnter your test input: ")
                    if user_input.lower() == 'exit':
                        continue
                        
                    # Test selected model
                    response = test_single_model(selected_model, user_input)
                    
                    # Format and display results
                    formatted_results = format_single_model_results(user_input, selected_model, response)
                    print("\n" + formatted_results)
                    
                    # Save results
                    save_results(formatted_results)
                    print("Results saved to results.txt")
                    
                elif input_method == "2":
                    # From file
                    try:
                        with open("input.txt", "r", encoding="utf-8") as f:
                            inputs = f.read().splitlines()
                        
                        if not inputs:
                            print("Error: input.txt is empty. Please add some inputs to the file.")
                            continue
                            
                        print(f"Found {len(inputs)} inputs in input.txt")
                        
                        for i, user_input in enumerate(inputs):
                            if not user_input.strip():  # Skip empty lines
                                continue
                                
                            print(f"\nProcessing input {i+1}/{len(inputs)}: {user_input[:50]}...")
                            
                            # Test selected model
                            response = test_single_model(selected_model, user_input)
                            
                            # Format and display results
                            formatted_results = format_single_model_results(user_input, selected_model, response)
                            print("\n" + formatted_results)
                            
                            # Save results
                            save_results(formatted_results)
                            print(f"Results for input {i+1} saved to results.txt")
                            
                            # Add delay between inputs (except after the last one)
                            if i < len(inputs) - 1:
                                print("Waiting 10 seconds before processing next input...")
                                time.sleep(10)
                        
                        print("All inputs from file processed successfully.")
                        
                    except FileNotFoundError:
                        print("Error: input.txt not found. Please create this file with your inputs.")
                
            except ValueError:
                print("Invalid input. Please enter a number.")
                
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main() 