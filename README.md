# Enhanced Reading Assessment Tool

A comprehensive web application for assessing English reading and grammar skills.

## Features

- **Text Input**: Upload PDF/TXT files or directly input text passages
- **Grammar Test**: Adaptive grammar assessment based on grade level
- **Reading Assessment**: Record and analyze reading performance
- **Comprehensive Analysis**: Detailed metrics including fluency, accuracy, and comprehension
- **Personalized Recommendations**: Custom feedback and next steps based on assessment results

## Setup

### Prerequisites

- Python 3.8+
- Node.js and npm (for front-end development)
- Whisper.cpp (for speech recognition)
- FFMPEG (for audio processing)

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/enhanced-reading-assessment.git
   cd enhanced-reading-assessment
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables (create a `.env` file):
   ```
   FLASK_SECRET_KEY=your_secret_key_here
   WHISPER_CPP_CLI_PATH=./whisper.cpp/build/bin/main
   WHISPER_CPP_MODEL_PATH=./whisper.cpp/models/ggml-base.en.bin
   ```

5. Run the application:
   ```
   python app.py
   ```

6. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

## Usage

1. **Enter Student Information**: Provide name and grade level
2. **Input Text**: Upload a file or enter text directly
3. **Complete Grammar Test**: Answer grammar questions
4. **Record Reading**: Read the passage aloud
5. **View Analysis**: Check comprehensive assessment results

## Technical Implementation

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript, Bootstrap 5
- **Speech Recognition**: Whisper.cpp (OpenAI's open-source model)
- **Text Processing**: Natural Language Processing techniques
- **Visualization**: Chart.js

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 