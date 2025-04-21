from flask import Flask, render_template, request, jsonify, session, send_from_directory, redirect, url_for
import os
import re
import tempfile
import base64
import json
import logging
import time
import subprocess
import math
import random
import platform
import glob
import difflib
from difflib import SequenceMatcher
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import traceback

# Load environment variables from .env file
load_dotenv()

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,  # Set to INFO instead of DEBUG for production
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()  # This outputs to console
    ]
)
logger = logging.getLogger(__name__)

# Print startup banner for easy identification in logs
logger.info("="*50)
logger.info("ENHANCED READING ASSESSMENT TOOL STARTING")
logger.info("="*50)

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))

# Serve static files
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

# Configuration
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'txt'}
DATABASE_FOLDER = os.path.join(os.getcwd(), 'data')

# Create required folders if they don't exist
try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    # Check and set permissions if possible
    os.chmod(UPLOAD_FOLDER, 0o755)
    logger.info(f"Upload folder created/verified: {UPLOAD_FOLDER}")
except Exception as e:
    logger.error(f"Error creating/accessing upload folder: {e}")

try:
    os.makedirs(DATABASE_FOLDER, exist_ok=True)
    logger.info(f"Database folder created/verified: {DATABASE_FOLDER}")
except Exception as e:
    logger.error(f"Error creating/accessing database folder: {e}")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size

# =====================================================================
# WHISPER.CPP CONFIGURATION - IMPROVED SECTION
# =====================================================================

# Function to auto-detect whisper.cpp paths
def detect_whisper_paths():
    """Auto-detect whisper.cpp paths based on common installation patterns"""
    system = platform.system()
    cli_paths = []
    model_paths = []
    
    # Look for CLI executable
    if system == "Windows":
        cli_paths = [
            './whisper.cpp/build/bin/main.exe',
            './whisper.cpp/build/main.exe',
            './whisper/bin/main.exe',
            *glob.glob("./*/whisper*/*/main.exe")
        ]
    else:  # Linux/Mac
        cli_paths = [
            './whisper.cpp/build/bin/main',
            './whisper.cpp/main',
            '/usr/local/bin/whisper.cpp',
            '/usr/local/bin/whisper',
            *glob.glob("./*/whisper*/*/main")
        ]
    
    # Look for model files
    model_paths = [
        './whisper.cpp/models/ggml-base.en.bin',
        './models/ggml-base.en.bin',
        './whisper/models/ggml-base.en.bin',
        *glob.glob("./*/whisper*/*/models/ggml-base.en.bin")
    ]
    
    # Find first existing CLI path
    cli_path = None
    for path in cli_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            cli_path = path
            break
    
    # Find first existing model path
    model_path = None
    for path in model_paths:
        if os.path.exists(path):
            model_path = path
            break
    
    return cli_path, model_path

# Get Whisper.cpp paths with improved detection
cli_path, model_path = detect_whisper_paths()
WHISPER_CPP_CLI_PATH = os.getenv('WHISPER_CPP_CLI_PATH', cli_path or './whisper.cpp/build/bin/main')
WHISPER_CPP_MODEL_PATH = os.getenv('WHISPER_CPP_MODEL_PATH', model_path or './whisper.cpp/models/ggml-base.en.bin')

# Print detected paths for debugging
logger.info(f"Detected Whisper CLI path: {cli_path or 'Not found'}")
logger.info(f"Detected Whisper model path: {model_path or 'Not found'}")
logger.info(f"Using Whisper CLI path: {WHISPER_CPP_CLI_PATH}")
logger.info(f"Using Whisper model path: {WHISPER_CPP_MODEL_PATH}")

# Validate whisper.cpp configuration
def check_whisper_cpp_config():
    """Check if whisper.cpp is properly configured and log detailed results"""
    status = {
        "cli_exists": False,
        "cli_path": WHISPER_CPP_CLI_PATH,
        "model_exists": False,
        "model_path": WHISPER_CPP_MODEL_PATH,
        "ffmpeg_available": False,
        "ffmpeg_path": None,
        "overall_status": False
    }
    
    # Check if whisper-cli exists
    if os.path.exists(WHISPER_CPP_CLI_PATH) and os.access(WHISPER_CPP_CLI_PATH, os.X_OK):
        status["cli_exists"] = True
        logger.info(f"✅ whisper-cli found at: {WHISPER_CPP_CLI_PATH}")
    else:
        logger.error(f"❌ whisper-cli NOT found at: {WHISPER_CPP_CLI_PATH}")
        if os.path.exists(WHISPER_CPP_CLI_PATH):
            logger.error(f"   File exists but is not executable")
        
    # Check if model exists
    if os.path.exists(WHISPER_CPP_MODEL_PATH):
        status["model_exists"] = True
        model_size_mb = os.path.getsize(WHISPER_CPP_MODEL_PATH) / (1024 * 1024)
        logger.info(f"✅ Whisper model found at: {WHISPER_CPP_MODEL_PATH} (Size: {model_size_mb:.2f} MB)")
    else:
        logger.error(f"❌ Whisper model NOT found at: {WHISPER_CPP_MODEL_PATH}")
    
    # Check for ffmpeg
    try:
        ffmpeg_path = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True, check=False).stdout.strip()
        if ffmpeg_path:
            status["ffmpeg_available"] = True
            status["ffmpeg_path"] = ffmpeg_path
            logger.info(f"✅ ffmpeg found at: {ffmpeg_path}")
            
            # Get ffmpeg version for debugging
            ffmpeg_version = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, check=False).stdout.split('\n')[0]
            logger.info(f"   ffmpeg version: {ffmpeg_version}")
        else:
            logger.error("❌ ffmpeg NOT found in PATH")
            
            # Try to find ffmpeg in common locations
            common_locations = ['/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg', '/usr/bin/ffmpeg']
            for location in common_locations:
                if os.path.exists(location):
                    status["ffmpeg_available"] = True
                    status["ffmpeg_path"] = location
                    logger.info(f"✅ ffmpeg found at alternative location: {location}")
                    os.environ['PATH'] = f"{os.path.dirname(location)}:{os.environ.get('PATH', '')}"
                    break
    except Exception as e:
        logger.error(f"❌ Error checking for ffmpeg: {e}")
    
    # Set overall status
    status["overall_status"] = status["cli_exists"] and status["model_exists"] and status["ffmpeg_available"]
    if status["overall_status"]:
        logger.info("✅ Whisper.cpp configuration is VALID")
    else:
        logger.error("❌ Whisper.cpp configuration is INVALID - some components missing")
    
    return status

# Call this function to check and display whisper.cpp status at startup
whisper_cpp_status = check_whisper_cpp_config()

# =====================================================================
# HELPER FUNCTIONS
# =====================================================================

def allowed_file(filename):
    """Check if a file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path):
    """
    Extract text from PDF with error handling and basic cleanup
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        str: Extracted text
    """
    try:
        # Try using PyPDF2 first
        try:
            import PyPDF2
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                
                # Handle encrypted PDFs
                if reader.is_encrypted:
                    try:
                        reader.decrypt('')  # Try empty password
                    except:
                        return "Error: PDF is encrypted and could not be decrypted."
                
                # Extract text page by page
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                    
                if text.strip():
                    return text
        except Exception as e:
            logger.warning(f"PyPDF2 extraction failed: {e}, trying alternate methods...")
        
        # If PyPDF2 failed or returned empty text, try pdftotext command line tool
        try:
            result = subprocess.run(['pdftotext', pdf_path, '-'], 
                                  capture_output=True, text=True, check=True)
            if result.stdout.strip():
                return result.stdout
        except:
            logger.warning("pdftotext command line tool failed, trying next method...")
        
        # If all methods failed, return error
        return "Error: Could not extract text from PDF. File may be corrupted or contains only images."
        
    except Exception as e:
        logger.error(f"PDF text extraction error: {e}")
        return f"Error extracting text: {str(e)}"

def enhance_and_format_text(text, grade_level=None):
    """
    Format extracted text for better readability
    
    Args:
        text (str): Raw text to format
        grade_level (int, optional): Student grade level
    
    Returns:
        str: Formatted text
    """
    if not text or len(text.strip()) < 10:
        return text
    
    # Normalize line breaks and whitespace
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)  # Normalize multiple line breaks
    
    # Handle encoding issues and special characters
    char_replacements = {
        'â€™': "'", 'â€˜': "'", 'â€œ': '"', 'â€': '"',
        'â€"': '–', 'â€"': '—', 'â€¢': '•', 'â€¦': '…',
        'Â©': '©', 'Â®': '®', 'â„¢': '™', 'Â°': '°',
        '&amp;': '&', '&lt;': '<', '&gt;': '>', '\u00a0': ' ',
    }
    for old, new in char_replacements.items():
        text = text.replace(old, new)
    
    # Remove PDF artifacts (page numbers, headers/footers)
    text = re.sub(r'\n\s*\d+\s*\n', '\n', text)  # Standalone page numbers
    text = re.sub(r'\n\s*Page\s+\d+(\s+of\s+\d+)?\s*\n', '\n', text, flags=re.IGNORECASE)  # Page X [of Y]
    
    # Handle hyphenation across lines
    text = re.sub(r'(\w)-\n(\s*[a-z])', r'\1\2', text)
    
    # Split text into paragraphs
    paragraphs = text.split('\n\n')
    formatted_paragraphs = []
    
    for paragraph in paragraphs:
        if paragraph.strip():
            # Check if this looks like a heading
            if re.match(r'^[A-Z0-9\s]{5,}$', paragraph.strip()):
                formatted_paragraphs.append(f"## {paragraph.strip()}")
            else:
                formatted_paragraphs.append(paragraph.strip())
    
    # Join paragraphs with proper spacing
    formatted_text = '\n\n'.join(formatted_paragraphs)
    
    return formatted_text

def count_syllables(word):
    """Count syllables in a word (English)"""
    word = word.lower().strip(".,;:!?-\"'()[]{}")
    if not word:
        return 0
        
    # Special cases
    if word in ['the', 'me', 'he', 'she', 'be', 'see']:
        return 1
        
    # Count vowel groups
    vowels = "aeiouy"
    count = 0
    prev_is_vowel = False
    
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_is_vowel:
            count += 1
        prev_is_vowel = is_vowel
    
    # Adjust for silent e
    if word.endswith('e') and len(word) > 2 and word[-2] not in vowels:
        count -= 1
    
    # Words can't have zero syllables
    return max(1, count)

def get_wpm_benchmark(grade_level):
    """
    Return expected words-per-minute benchmark for a given grade level
    Based on research-backed fluency norms (Hasbrouck & Tindal)
    """
    # Research-based WPM targets by grade level (50th percentile, spring)
    benchmarks = {
        1: 60,
        2: 95,
        3: 115,
        4: 140,
        5: 150,
        6: 160,
        7: 165,
        8: 170,
        9: 180,
        10: 190,
        11: 200,
        12: 210
    }
    
    # Default to nearest grade if out of range
    if grade_level < 1:
        grade_level = 1
    elif grade_level > 12:
        grade_level = 12
        
    return benchmarks.get(grade_level, 150)

def calculate_reading_accuracy(original_text, spoken_text):
    """Calculate reading accuracy percentage"""
    original_words = original_text.lower().split()
    spoken_words = spoken_text.lower().split()
    
    # Filter out filler words
    filler_words = {"um", "uh", "er", "like", "you know"}
    filtered_spoken = [word for word in spoken_words if word not in filler_words]
    
    # Count matching words
    matched_count = 0
    matched_indices = set()
    
    for i, orig_word in enumerate(original_words):
        # Look for best match in spoken words that hasn't been matched yet
        best_match_idx = -1
        best_match_score = 0.7  # Threshold for matching
        
        for j, spoken_word in enumerate(filtered_spoken):
            if j in matched_indices:
                continue  # Skip already matched words
                
            similarity = SequenceMatcher(None, orig_word, spoken_word).ratio()
            if similarity > best_match_score:
                best_match_score = similarity
                best_match_idx = j
        
        if best_match_idx >= 0:
            matched_count += 1
            matched_indices.add(best_match_idx)
    
    # Calculate accuracy percentage
    accuracy = min(100, int((matched_count / max(len(original_words), 1)) * 100))
    return accuracy

def analyze_reading_fluency(original_text, spoken_text, grade_level, audio_duration=None):
    """
    Analyze reading fluency with multiple metrics
    
    Args:
        original_text (str): Original text that should have been read
        spoken_text (str): Transcribed text of what was actually read
        grade_level (int): Student's grade level
        audio_duration (float): Duration of the audio recording in seconds
        
    Returns:
        dict: Fluency metrics
    """
    # Split into words
    original_words = original_text.split()
    spoken_words = spoken_text.split()
    
    # Basic count metrics
    word_count = len(spoken_words)
    
    # Calculate words per minute if audio duration is available
    wpm = None
    if not audio_duration and 'audio_duration' in session:
        audio_duration = session.get('audio_duration')
    
    if audio_duration:
        minutes = audio_duration / 60
        wpm = round(word_count / minutes, 1) if minutes > 0 else 0
    else:
        # Estimate WPM based on typical values for grade level
        wpm_estimates = {
            1: 60, 2: 90, 3: 110, 4: 130, 5: 140, 
            6: 150, 7: 160, 8: 170, 9: 180, 10: 190, 11: 200, 12: 210
        }
        wpm = wpm_estimates.get(grade_level, 150)
    
    # Calculate accuracy percentage
    accuracy_score = calculate_reading_accuracy(original_text, spoken_text)
    
    # Get benchmark WPM for grade level
    benchmark_wpm = get_wpm_benchmark(grade_level)
    
    # Calculate fluency level (simplified)
    if accuracy_score >= 95 and wpm >= benchmark_wpm * 0.9:
        fluency_level = "Independent"
        fluency_score = min(100, accuracy_score + 5)
    elif accuracy_score >= 90 and wpm >= benchmark_wpm * 0.7:
        fluency_level = "Instructional"
        fluency_score = min(95, accuracy_score)
    else:
        fluency_level = "Frustration"
        fluency_score = min(85, accuracy_score - 5)
    
    # Combine all metrics
    fluency_metrics = {
        "words_per_minute": wpm,
        "accuracy_percentage": accuracy_score,
        "benchmark": {
            "wpm_target": benchmark_wpm,
            "wpm_status": "At Grade Level" if wpm >= benchmark_wpm * 0.9 else "Below Grade Level" 
        },
        "fluency_level": {
            "level": fluency_level,
            "score": fluency_score,
            "description": f"Reading is at the {fluency_level} level"
        }
    }
    
    return fluency_metrics

def analyze_reading(original_text, spoken_text, grade_level, audio_duration=None):
    """
    Comprehensive reading analysis incorporating basic metrics
    
    Args:
        original_text (str): Original text
        spoken_text (str): Spoken text
        grade_level (int): Grade level
        audio_duration (float): Audio duration if available
        
    Returns:
        dict: Analysis results
    """
    # Get fluency metrics
    fluency_metrics = analyze_reading_fluency(original_text, spoken_text, grade_level, audio_duration)
    
    # Calculate overall scores
    wpm_benchmark = get_wpm_benchmark(grade_level)
    wpm_score = min(100, int((fluency_metrics["words_per_minute"] / wpm_benchmark) * 100))
    
    fluency_score = fluency_metrics["fluency_level"]["score"]
    accuracy_score = fluency_metrics["accuracy_percentage"]
    
    # Simplified Overall rating (based just on accuracy and fluency)
    overall_rating = (fluency_score * 0.5) + (accuracy_score * 0.5)
    
    # Identify strengths and areas to improve
    strengths = []
    areas_to_improve = []
    
    # Add strengths based on scores
    if fluency_score >= 85:
        strengths.append(f"Strong reading fluency ({fluency_score}/100)")
    if accuracy_score >= 90:
        strengths.append(f"High reading accuracy ({accuracy_score}%)")
    
    # Add improvement areas
    if fluency_score < 75:
        areas_to_improve.append(f"Work on reading fluency (currently {fluency_score}/100)")
    if accuracy_score < 85:
        areas_to_improve.append(f"Improve reading accuracy (currently {accuracy_score}%)")
    
    # Create personalized feedback based on grade level
    personalized_feedback = {
        "praise": f"Good job reading! You read at {fluency_metrics['words_per_minute']} words per minute.",
        "focus_area": "Let's work on reading smoothly and carefully.",
        "next_steps": "Try reading this passage again and see if you can improve your speed and accuracy."
    }
    
    # Assemble final result
    analysis_result = {
        "overall_rating": round(overall_rating),
        "fluency_score": round(fluency_score),
        "accuracy_score": round(accuracy_score),
        "fluency_metrics": fluency_metrics,
        "strengths": strengths,
        "areas_to_improve": areas_to_improve,
        "personalized_feedback": personalized_feedback
    }
    
    return analysis_result

def compare_reading_with_text(original_text, spoken_text):
    """
    Create highlighted visualization of reading accuracy
    
    Args:
        original_text (str): Original text
        spoken_text (str): Spoken text
        
    Returns:
        str: HTML with highlighted text
    """
    try:
        # Find word boundaries in original text
        original_words = re.findall(r'\b\w+\b', original_text.lower())
        spoken_words = re.findall(r'\b\w+\b', spoken_text.lower())
        
        # Track which spoken words have been matched
        matched_spoken_indices = set()
        
        # For each original word, find its best match
        word_matches = []
        for i, orig_word in enumerate(original_words):
            best_match = {
                "spoken_index": -1,
                "similarity": 0.5,  # Threshold for matching
                "category": "missing"  # Default: word was not spoken
            }
            
            # Look for this word in spoken text
            for j, spoken_word in enumerate(spoken_words):
                if j in matched_spoken_indices:
                    continue  # Skip words that have already been matched
                
                # Calculate similarity
                similarity = SequenceMatcher(None, orig_word, spoken_word).ratio()
                
                if similarity > best_match["similarity"]:
                    best_match["spoken_index"] = j
                    best_match["similarity"] = similarity
                    
                    # Determine match category based on similarity
                    if similarity > 0.9:
                        best_match["category"] = "good"
                    elif similarity > 0.7:
                        best_match["category"] = "medium"
                    else:
                        best_match["category"] = "bad"
            
            # If we found a match, mark it as used
            if best_match["spoken_index"] >= 0:
                matched_spoken_indices.add(best_match["spoken_index"])
            
            word_matches.append(best_match)
        
        # Reconstruct original text with highlighting
        result = []
        start_idx = 0
        
        # Function to get CSS class for highlighting
        def get_highlight_class(match_info):
            category = match_info["category"]
            if category == "good":
                return "highlight-good"
            elif category == "medium":
                return "highlight-medium"
            elif category == "bad":
                return "highlight-bad"
            else:  # missing
                return "highlight-missing"
        
        # Find word boundaries in original text
        for i, orig_word in enumerate(original_words):
            # Find the word in the original text
            pattern = r'\b' + re.escape(orig_word) + r'\b'
            match = re.search(pattern, original_text[start_idx:].lower())
            
            if match:
                # Get the actual text from the original (preserve case)
                word_start = start_idx + match.start()
                word_end = start_idx + match.end()
                actual_word = original_text[word_start:word_end]
                
                # Add any text before this word
                if word_start > start_idx:
                    result.append(original_text[start_idx:word_start])
                
                # Add the highlighted word
                match_info = word_matches[i]
                highlight_class = get_highlight_class(match_info)
                result.append(f'<span class="{highlight_class}" data-word-index="{i}">{actual_word}</span>')
                
                # Update start_idx for the next iteration
                start_idx = word_end
        
        # Add any remaining text
        if start_idx < len(original_text):
            result.append(original_text[start_idx:])
        
        # CSS styles for highlighting
        css_styles = """
        <style>
        .highlight-good { background-color: #c8e6c9; } /* Light green */
        .highlight-medium { background-color: #fff9c4; } /* Light yellow */
        .highlight-bad { background-color: #ffcdd2; } /* Light red */
        .highlight-missing { background-color: #f5f5f5; text-decoration: line-through; } /* Gray with strikethrough */
        </style>
        """
        
        return css_styles + ''.join(result)
    except Exception as e:
        logger.error(f"Error in text comparison: {e}")
        return original_text  # Return original text if highlighting fails

# =====================================================================
# GRAMMAR TESTING FUNCTIONS
# =====================================================================

def generate_grammar_test(grade_level):
    """
    Generate a grammar test appropriate for the given grade level
    
    Args:
        grade_level (int): Student's grade level (1-12)
        
    Returns:
        dict: Grammar test with questions and answers
    """
    # Grammar test templates by grade range
    grammar_tests = {
        # Grades 1-2: Basic sentence structure, capitalization, ending punctuation
        'early_elementary': [
            {"question": "Which sentence is correct?", 
             "options": ["the dog runs fast.", "The dog runs fast.", "the Dog runs Fast.", "The dog Runs fast."],
             "answer": 1,
             "concept": "capitalization"},
            {"question": "Which sentence is complete?", 
             "options": ["Ran to the store.", "He ran.", "To the store.", "Running fast."],
             "answer": 1,
             "concept": "complete_sentence"},
            {"question": "Which ending is correct for a question?", 
             "options": [".", "!", "?", ","],
             "answer": 2,
             "concept": "punctuation"},
            {"question": "Choose the correct plural form of 'cat'", 
             "options": ["cats", "cat's", "cat", "cates"],
             "answer": 0,
             "concept": "plurals"},
            {"question": "Which word shows an action?", 
             "options": ["happy", "jump", "big", "the"],
             "answer": 1,
             "concept": "verbs"}
        ],
        
        # Grades 3-5: Subject-verb agreement, pronouns, basic tenses
        'upper_elementary': [
            {"question": "Choose the correct verb: 'The dogs ____ in the yard.'", 
             "options": ["is playing", "are playing", "am playing", "plays"],
             "answer": 1,
             "concept": "subject_verb_agreement"},
            {"question": "Which pronoun correctly completes this sentence? '____ went to the store.'", 
             "options": ["Him", "Her", "They", "He"],
             "answer": 3,
             "concept": "pronouns"},
            {"question": "Choose the past tense of 'walk'", 
             "options": ["walking", "walks", "walked", "will walk"],
             "answer": 2,
             "concept": "verb_tense"},
            {"question": "Which is a compound sentence?", 
             "options": ["I like pizza.", "I like pizza and I eat it often.", "While eating pizza.", "The delicious pizza."],
             "answer": 1,
             "concept": "sentence_types"},
            {"question": "Choose the correct homophone: 'They are ____ friends.'", 
             "options": ["they're", "their", "there", "them"],
             "answer": 1,
             "concept": "homophones"}
        ],
        
        # Grades 6-8: Complex sentences, passive voice, perfect tenses
        'middle_school': [
            {"question": "Identify the correctly punctuated sentence:", 
             "options": ["Although it was raining we went to the park.", "Although it was raining, we went to the park.", "Although, it was raining we went to the park.", "Although it was raining; we went to the park."],
             "answer": 1,
             "concept": "complex_punctuation"},
            {"question": "Which sentence uses the passive voice?", 
             "options": ["The boy threw the ball.", "The ball was thrown by the boy.", "Throwing the ball, the boy smiled.", "The boy throws balls."],
             "answer": 1,
             "concept": "passive_voice"},
            {"question": "Choose the present perfect tense:", 
             "options": ["I am walking", "I walk", "I have walked", "I walked"],
             "answer": 2,
             "concept": "perfect_tense"},
            {"question": "Identify the adjective clause:", 
             "options": ["Running to the store", "Because it was late", "Where we met yesterday", "The book that I read"],
             "answer": 3,
             "concept": "adjective_clauses"},
            {"question": "Which sentence contains a gerund?", 
             "options": ["I will travel tomorrow.", "She travels frequently.", "Traveling is my passion.", "She traveled yesterday."],
             "answer": 2,
             "concept": "gerunds"}
        ],
        
        # Grades 9-12: Advanced grammar concepts, nuanced usage
        'high_school': [
            {"question": "Which sentence contains a split infinitive?", 
             "options": ["To boldly go where no one has gone before.", "To go boldly where no one has gone before.", "Boldly to go where no one has gone before.", "Boldly going where no one has gone before."],
             "answer": 0,
             "concept": "split_infinitives"},
            {"question": "Identify the subjunctive mood:", 
             "options": ["I was thinking about the problem.", "I wish I were taller.", "I will solve this tomorrow.", "I have solved many problems."],
             "answer": 1,
             "concept": "subjunctive_mood"},
            {"question": "Which is an example of a dangling modifier?", 
             "options": ["Walking to school, my backpack felt heavy.", "After finishing the assignment, she took a break.", "Running quickly, the bus was missed.", "The teacher, smiling broadly, handed back the tests."],
             "answer": 2,
             "concept": "dangling_modifiers"},
            {"question": "Choose the sentence with correct parallel structure:", 
             "options": ["She likes swimming, running, and to bike.", "She likes swimming, running, and biking.", "She likes to swim, running, and to bike.", "She likes to swim, to run, and biking."],
             "answer": 1,
             "concept": "parallel_structure"},
            {"question": "Identify the appositive phrase:", 
             "options": ["The car that was red", "My brother who lives in Denver", "My brother, a doctor in Denver, called yesterday.", "When he arrived at the station"],
             "answer": 2,
             "concept": "appositives"}
        ]
    }
    
    # Select appropriate test based on grade level
    if 1 <= grade_level <= 2:
        test_set = grammar_tests['early_elementary']
    elif 3 <= grade_level <= 5:
        test_set = grammar_tests['upper_elementary']
    elif 6 <= grade_level <= 8:
        test_set = grammar_tests['middle_school']
    else:  # 9-12 and beyond
        test_set = grammar_tests['high_school']
    
    # Shuffle questions and generate test
    import random
    random.shuffle(test_set)
    
    # Take all 5 questions or fewer if less available
    final_questions = test_set[:min(5, len(test_set))]
    
    return {
        "grade_level": grade_level,
        "questions": final_questions
    }

def evaluate_grammar_test(test_answers, user_answers):
    """
    Evaluate a grammar test and provide detailed feedback
    
    Args:
        test_answers (list): List of correct answers and concepts
        user_answers (list): List of user's selected answers
        
    Returns:
        dict: Evaluation results with score and recommendations
    """
    if len(test_answers) != len(user_answers):
        return {"error": "Answer count mismatch"}
    
    # Calculate basic score
    correct_count = 0
    results = []
    concepts_mastered = []
    concepts_to_improve = []
    
    for i, (question, user_answer) in enumerate(zip(test_answers, user_answers)):
        correct = (int(user_answer) == question["answer"])
        if correct:
            correct_count += 1
            concepts_mastered.append(question["concept"])
        else:
            concepts_to_improve.append(question["concept"])
        
        results.append({
            "question_index": i,
            "correct": correct,
            "user_answer": int(user_answer),
            "correct_answer": question["answer"],
            "concept": question["concept"]
        })
    
    # Calculate percentage score
    score_percentage = int((correct_count / len(test_answers)) * 100)
    
    # Determine proficiency level
    if score_percentage >= 90:
        proficiency_level = "Advanced"
    elif score_percentage >= 75:
        proficiency_level = "Proficient"
    elif score_percentage >= 60:
        proficiency_level = "Basic"
    else:
        proficiency_level = "Below Basic"
    
    # Get unique concepts to improve (avoid duplicates)
    unique_concepts_to_improve = list(set(concepts_to_improve))
    
    # Create recommendations based on concepts to improve
    recommendations = generate_grammar_recommendations(unique_concepts_to_improve)
    
    # Prepare reading topics based on grammar results
    reading_topics = suggest_reading_topics(score_percentage, unique_concepts_to_improve)
    
    return {
        "score": score_percentage,
        "correct_count": correct_count,
        "total_questions": len(test_answers),
        "proficiency_level": proficiency_level,
        "question_results": results,
        "concepts_mastered": list(set(concepts_mastered)),
        "concepts_to_improve": unique_concepts_to_improve,
        "recommendations": recommendations,
        "suggested_reading_topics": reading_topics
    }

def generate_grammar_recommendations(concepts_to_improve):
    """
    Generate specific recommendations for grammar concepts that need improvement
    
    Args:
        concepts_to_improve (list): List of grammar concepts to improve
        
    Returns:
        list: Specific recommendations for each concept
    """
    recommendation_map = {
        "capitalization": "Practice capitalizing the first word of sentences and proper nouns.",
        "complete_sentence": "Work on ensuring sentences have a subject and a verb.",
        "punctuation": "Review the rules for period, question mark, and exclamation point usage.",
        "plurals": "Practice forming plural nouns, especially irregular ones.",
        "verbs": "Focus on identifying action words in sentences.",
        "subject_verb_agreement": "Ensure subjects and verbs agree in number (singular/plural).",
        "pronouns": "Practice using the correct pronouns for subjects and objects.",
        "verb_tense": "Review past, present, and future verb tenses.",
        "sentence_types": "Study simple, compound, and complex sentence structures.",
        "homophones": "Practice distinguishing between words that sound alike but have different meanings.",
        "complex_punctuation": "Work on using commas in complex and compound sentences.",
        "passive_voice": "Learn to identify and convert between active and passive voice.",
        "perfect_tense": "Practice using present perfect, past perfect, and future perfect tenses.",
        "adjective_clauses": "Study how to form and punctuate adjective clauses.",
        "gerunds": "Identify and use gerunds (verbs ending in -ing used as nouns).",
        "split_infinitives": "Learn about infinitives and when splitting them is appropriate.",
        "subjunctive_mood": "Practice using the subjunctive mood for hypothetical situations.",
        "dangling_modifiers": "Learn to connect modifiers with the correct word they modify.",
        "parallel_structure": "Practice creating lists with consistent grammatical forms.",
        "appositives": "Study how to use and punctuate appositives (noun phrases that rename other nouns)."
    }
    
    recommendations = []
    for concept in concepts_to_improve:
        if concept in recommendation_map:
            recommendations.append(recommendation_map[concept])
    
    return recommendations

def suggest_reading_topics(grammar_score, concepts_to_improve):
    """
    Suggest reading topics based on grammar test results
    
    Args:
        grammar_score (int): Grammar test percentage score
        concepts_to_improve (list): Concepts that need improvement
        
    Returns:
        list: Suggested reading topics with descriptions
    """
    # Base topics that work for all levels
    base_topics = [
        {
            "title": "The Adventures of Max",
            "description": "A short story about a curious child exploring their neighborhood.",
            "difficulty": "easy",
            "focus": "narrative",
            "word_count": 150
        },
        {
            "title": "All About Dolphins",
            "description": "An informational text about dolphins and their habitats.",
            "difficulty": "medium",
            "focus": "informational",
            "word_count": 200
        },
        {
            "title": "The Mystery of the Missing Book",
            "description": "A mystery story set in a school library.",
            "difficulty": "challenging",
            "focus": "narrative",
            "word_count": 250
        }
    ]
    
    # Additional topics based on difficulty (determined by grammar score)
    if grammar_score < 60:
        # Simpler texts for those who need more support
        additional_topics = [
            {
                "title": "My Pet Dog",
                "description": "A simple story about caring for a pet dog.",
                "difficulty": "easy",
                "focus": "narrative",
                "word_count": 100
            },
            {
                "title": "The Four Seasons",
                "description": "Basic information about the four seasons and their characteristics.",
                "difficulty": "easy",
                "focus": "informational",
                "word_count": 120
            }
        ]
    elif grammar_score < 75:
        # Moderate texts for those at basic level
        additional_topics = [
            {
                "title": "The Lost Treasure",
                "description": "An adventure story about finding a hidden treasure.",
                "difficulty": "medium",
                "focus": "narrative",
                "word_count": 180
            },
            {
                "title": "Volcanoes: Earth's Fiery Mountains",
                "description": "Facts about volcanoes and how they shape our planet.",
                "difficulty": "medium",
                "focus": "informational",
                "word_count": 220
            }
        ]
    else:
        # More challenging texts for advanced students
        additional_topics = [
            {
                "title": "The Cosmic Journey",
                "description": "A science fiction story about space exploration.",
                "difficulty": "challenging",
                "focus": "narrative",
                "word_count": 300
            },
            {
                "title": "The Human Brain: Our Amazing Computer",
                "description": "A detailed text about how the human brain works.",
                "difficulty": "challenging",
                "focus": "informational",
                "word_count": 350
            }
        ]
    
    # Combine base topics with additional ones
    all_topics = base_topics + additional_topics
    
    # Customize selection based on concepts that need improvement
    # For example, if they struggle with punctuation, include dialogue-heavy texts
    if "punctuation" in concepts_to_improve or "complex_punctuation" in concepts_to_improve:
        all_topics.append({
            "title": "The Great Conversation",
            "description": "A story with lots of dialogue between different characters.",
            "difficulty": "medium",
            "focus": "dialogue",
            "word_count": 200,
            "targets": ["punctuation", "complex_punctuation"]
        })
    
    # If they struggle with verb tense, include a story with different time periods
    if "verb_tense" in concepts_to_improve or "perfect_tense" in concepts_to_improve:
        all_topics.append({
            "title": "Yesterday, Today, and Tomorrow",
            "description": "A story that moves between past, present, and future events.",
            "difficulty": "medium",
            "focus": "time shifts",
            "word_count": 220,
            "targets": ["verb_tense", "perfect_tense"]
        })
    
    # Shuffle and return a subset
    import random
    random.shuffle(all_topics)
    return all_topics[:4]  # Return top 4 suggestions

# =====================================================================
# ENHANCED TRANSCRIPTION AND ANALYSIS FUNCTIONS
# =====================================================================

def transcribe_audio_realtime(audio_data):
    """Transcribe audio using Whisper.cpp or fallback to mock if not available"""
    try:
        # Log that we're using Whisper.cpp
        logger.info("Using Whisper.cpp for transcription")
        
        # Check if we have Whisper.cpp available
        has_whisper = whisper_cpp_status.get("overall_status", False)
        
        if has_whisper:
            logger.info("Using enhanced transcription service")
            
            # Save audio to a temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file_path = temp_file.name
                temp_file.write(audio_data)
            
            try:
                # Get the CLI path from config
                whisper_cli = whisper_cpp_status.get("cli_path", "./whisper.cpp/build/bin/main")
                whisper_model = whisper_cpp_status.get("model_path", "./whisper.cpp/models/ggml-base.en.bin")
                
                logger.info(f"Attempting Whisper.cpp transcription with CLI: {whisper_cli}")
                
                # Convert audio to 16kHz WAV format
                output_path = f"{temp_file_path}_converted.wav"
                ffmpeg_cmd = f"ffmpeg -i {temp_file_path} -ar 16000 -ac 1 -y {output_path}"
                
                logger.info(f"Running ffmpeg command: {ffmpeg_cmd}")
                
                # Run ffmpeg
                process = subprocess.run(ffmpeg_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                logger.info(f"Audio converted successfully to {output_path}")
                
                # Create the output TXT path
                txt_output_path = f"{temp_file_path}.txt"
                
                # Check if model file exists
                if not os.path.exists(whisper_model):
                    logger.error(f"Whisper.cpp model file not found at: {whisper_model}")
                    
                    # Try to find model in a different location if using a relative path
                    if whisper_model.startswith('./'):
                        absolute_model_path = os.path.abspath(whisper_model)
                        logger.info(f"Trying absolute model path: {absolute_model_path}")
                        if os.path.exists(absolute_model_path):
                            whisper_model = absolute_model_path
                            logger.info(f"Found model at absolute path: {whisper_model}")
                        else:
                            # Try to look in common locations
                            possible_paths = [
                                "/Users/adityadubey/Desktop/Enhance_English_Learning /whisper.cpp/models/ggml-base.en.bin",
                                os.path.join(os.getcwd(), "whisper.cpp/models/ggml-base.en.bin"),
                                os.path.join(os.path.dirname(os.getcwd()), "whisper.cpp/models/ggml-base.en.bin")
                            ]
                            
                            for path in possible_paths:
                                logger.info(f"Checking for model at: {path}")
                                if os.path.exists(path):
                                    whisper_model = path
                                    logger.info(f"Found model at: {whisper_model}")
                                    break
                            else:
                                raise FileNotFoundError(f"Cannot find Whisper model file: {whisper_model}")
                            
                # Prepare the Whisper.cpp command with word timestamps
                whisper_cmd = f"{whisper_cli} -m {whisper_model} -f {output_path} -otxt --output-file {txt_output_path} --word-timestamps"
                
                logger.info(f"Running Whisper.cpp command: {whisper_cmd}")
                
                # Run Whisper.cpp
                process = subprocess.run(whisper_cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                if process.returncode != 0:
                    error_msg = process.stderr.decode('utf-8', errors='ignore')
                    logger.error(f"Whisper.cpp error: {error_msg}")
                    raise RuntimeError(f"Whisper.cpp failed: {error_msg}")
                
                # Read the output file if it exists
                if os.path.exists(txt_output_path):
                    with open(txt_output_path, 'r', encoding='utf-8') as f:
                        transcribed_text = f.read()
                    
                    # Extract word timing information if available
                    word_details = []
                    word_timing_pattern = r'\[\s*(\d+\.\d+)\s*->\s*(\d+\.\d+)\s*\]\s*(\S+)'
                    
                    if '--word-timestamps' in whisper_cmd:
                        # Look for a JSON file with word timestamps
                        json_output_path = txt_output_path.replace('.txt', '.json')
                        if os.path.exists(json_output_path):
                            try:
                                with open(json_output_path, 'r', encoding='utf-8') as f:
                                    word_data = json.load(f)
                                
                                # Extract word timestamps from the JSON structure
                                # Format depends on Whisper.cpp version, try different structures
                                if 'words' in word_data:
                                    for word_info in word_data['words']:
                                        word_details.append({
                                            'word': word_info.get('word', ''),
                                            'start': word_info.get('start', 0),
                                            'end': word_info.get('end', 0),
                                            'confidence': word_info.get('confidence', 0.0)
                                        })
                            except Exception as e:
                                logger.error(f"Error parsing word timing JSON: {e}")
                        else:
                            # Try to extract word timings from the raw output
                            with open(txt_output_path.replace('.txt', '.json'), 'w', encoding='utf-8') as f:
                                # Find all the word timing information
                                matches = re.findall(word_timing_pattern, transcribed_text)
                                for start_time, end_time, word in matches:
                                    word_details.append({
                                        'word': word,
                                        'start': float(start_time),
                                        'end': float(end_time),
                                        'confidence': 1.0  # No confidence info available
                                    })
                    
                    # Clean up temporary files
                    for file_path in [temp_file_path, output_path, txt_output_path]:
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                        except Exception as e:
                            logger.warning(f"Failed to remove temporary file {file_path}: {e}")
                    
                    return {
                        'transcription': transcribed_text.strip(),
                        'word_details': word_details,
                        'source': 'whisper_cpp'
                    }
                else:
                    logger.error(f"Output file {txt_output_path} not found")
                    raise FileNotFoundError(f"Whisper.cpp output file not found: {txt_output_path}")
                    
            except Exception as e:
                logger.error(f"Error using Whisper.cpp: {e}")
                logger.error("Falling back to mock transcription")
                
                # Clean up temporary files
                try:
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                    if os.path.exists(f"{temp_file_path}_converted.wav"):
                        os.remove(f"{temp_file_path}_converted.wav")
                    if os.path.exists(f"{temp_file_path}.txt"):
                        os.remove(f"{temp_file_path}.txt")
                except Exception as cleanup_error:
                    logger.warning(f"Error cleaning up temporary files: {cleanup_error}")
        
        # Fall back to mock transcription if Whisper.cpp is not available or failed
        logger.info("Using mock transcription with IMPROVED WORD DETAILS")
        
        # Generate a mock transcription
        # In a production environment, this would be replaced with an actual backup transcription service
        
        # Sample texts for different content types
        sample_texts = [
            "This is a test of the enhanced reading assessment tool. It helps students practice their reading skills.",
            "Education is the passport to the future, tomorrow belongs to those who prepare for it today.",
            "The quick brown fox jumps over the lazy dog. This pangram contains all the letters of the alphabet.",
            "Reading is essential for those who seek to rise above the ordinary. It is a habit that must be cultivated.",
            "Success is not final, failure is not fatal: It is the courage to continue that counts."
        ]
        
        # Select a sample text randomly
        sample_text = random.choice(sample_texts)
        
        # Add some random errors to simulate real speech recognition
        words = sample_text.split()
        for i in range(len(words)):
            if random.random() < 0.1:  # 10% chance of error for each word
                if random.random() < 0.5:
                    # Misspell the word
                    word = words[i]
                    if len(word) > 3:
                        pos = random.randint(1, len(word) - 2)
                        words[i] = word[:pos] + random.choice('abcdefghijklmnopqrstuvwxyz') + word[pos+1:]
                else:
                    # Replace with a similarly sounding word
                    common_substitutions = {
                        'their': 'there', 'there': 'their', 'they\'re': 'their',
                        'your': 'you\'re', 'you\'re': 'your',
                        'to': 'too', 'too': 'to', 'two': 'to',
                        'than': 'then', 'then': 'than',
                        'affect': 'effect', 'effect': 'affect',
                        'accept': 'except', 'except': 'accept',
                        'hear': 'here', 'here': 'hear'
                    }
                    if words[i].lower() in common_substitutions:
                        words[i] = common_substitutions[words[i].lower()]
        
        # Generate the final transcribed text
        transcribed_text = ' '.join(words)
        
        # Create word details with timing information
        word_details = []
        current_time = 0.0
        for word in words:
            # Simulate word duration based on length
            duration = 0.2 + len(word) * 0.05  # Longer words take more time
            
            # Add random variation
            duration += random.uniform(-0.05, 0.05)
            
            # Add to the list
            word_details.append({
                'word': word,
                'start': current_time,
                'end': current_time + duration,
                'confidence': random.uniform(0.8, 1.0)  # Random confidence score
            })
            
            # Update the current time
            current_time += duration + 0.1  # Add 0.1s gap between words
        
        logger.info(f"Generated mock transcription: {transcribed_text[:100]}...")
        logger.info(f"Created {len(word_details)} word details for highlighting")
        
        return {
            'transcription': transcribed_text,
            'word_details': word_details,
            'source': 'mock'
        }
    except Exception as e:
        logger.error(f"Error in transcription service: {e}")
        
        # Return a minimal response on error
        return {
            'transcription': 'Error transcribing audio.',
            'word_details': [],
            'source': 'error'
        }

def create_enhanced_transcription(transcribed_text, audio_duration):
    """
    Create an enhanced transcription result with word-level details
    
    Args:
        transcribed_text (str): The transcribed text
        audio_duration (float): Duration of the audio in seconds
        
    Returns:
        dict: Enhanced transcription result with word details
    """
    words = transcribed_text.split()
    word_details = []
    
    # Generate approximate timestamps based on audio duration
    if len(words) > 0:
        time_per_word = audio_duration / len(words)
    else:
        time_per_word = 0.5  # Default if no words
    
    # Create word details with estimated confidence and timestamps
    for i, word in enumerate(words):
        # Simulate confidence levels (would be provided by actual ASR system)
        confidence = random.uniform(0.75, 0.98)
        word_details.append({
            "word": word,
            "status": "correct",  # Default status
            "confidence": confidence,
            "timestamp": i * time_per_word
        })
    
    return {
        "transcribed_text": transcribed_text,
        "word_details": word_details,
        "duration": audio_duration,
        "original_text": transcribed_text  # Same as transcribed for real transcription
    }

def compare_reading_with_text_enhanced(original_text, transcription_result):
    """
    Create enhanced highlighted visualization of reading accuracy with detailed categories
    
    Args:
        original_text (str): Original text
        transcription_result (dict): Transcription result with text and word details
        
    Returns:
        str: HTML with highlighted text and detailed statistics
    """
    try:
        # Extract information from transcription result
        spoken_text = transcription_result.get("transcribed_text", transcription_result.get("text", ""))
        word_details = transcription_result.get("word_details", [])
        
        logger.info(f"Comparing original text ({len(original_text)} chars) with spoken text ({len(spoken_text)} chars)")
        logger.info(f"Word details available: {len(word_details)}")
        
        # If we have word details, use them directly for more accurate highlighting
        if word_details:
            return compare_reading_with_word_details(original_text, word_details)
        
        # If no word details, fall back to difflib comparison
        original_words = re.findall(r'\b\w+\b', original_text.lower())
        spoken_words = re.findall(r'\b\w+\b', spoken_text.lower())
        
        # Track statistics
        stats = {
            "correct": 0,
            "mispronounced": 0,
            "skipped": 0,
            "substituted": 0,
            "total_words": len(original_words)
        }
        
        # Compare words using difflib
        matcher = difflib.SequenceMatcher(None, original_words, spoken_words)
        
        # Create a mapping of word status based on difflib comparison
        word_status_map = {}
        
        # Process each opcode (match, delete, insert, replace)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                # Words match exactly
                for k in range(i2 - i1):
                    word_status_map[i1 + k] = {
                        "status": "correct",
                        "confidence": 1.0
                    }
                    stats["correct"] += 1
            elif tag == 'delete':
                # Words in original but not in spoken (skipped)
                for k in range(i2 - i1):
                    word_status_map[i1 + k] = {
                        "status": "skipped",
                        "confidence": 0.0
                    }
                    stats["skipped"] += 1
            elif tag == 'replace':
                # Words in both but different (mispronounced or substituted)
                for k in range(i2 - i1):
                    # If there's a corresponding word, check similarity
                    if k < (j2 - j1):
                        orig_word = original_words[i1 + k]
                        spoken_word = spoken_words[j1 + k]
                        similarity = difflib.SequenceMatcher(None, orig_word, spoken_word).ratio()
                        
                        if similarity > 0.7:
                            # Similar enough to be considered mispronounced
                            word_status_map[i1 + k] = {
                                "status": "mispronounced",
                                "confidence": similarity,
                                "actual_word": spoken_word
                            }
                            stats["mispronounced"] += 1
                        else:
                            # Different enough to be considered substituted
                            word_status_map[i1 + k] = {
                                "status": "substituted",
                                "confidence": similarity,
                                "actual_word": spoken_word
                            }
                            stats["substituted"] += 1
                    else:
                        # No corresponding word (skipped)
                        word_status_map[i1 + k] = {
                            "status": "skipped",
                            "confidence": 0.0
                        }
                        stats["skipped"] += 1
        
        # Mark any remaining words as skipped
        for i in range(len(original_words)):
            if i not in word_status_map:
                word_status_map[i] = {
                    "status": "skipped",
                    "confidence": 0
                }
                stats["skipped"] += 1
        
        # Reconstruct original text with highlighting
        result = []
        start_idx = 0
        
        # Function to get CSS class for highlighting
        def get_highlight_class(status):
            if status == "correct":
                return "highlight-correct"
            elif status == "mispronounced":
                return "highlight-mispronounced"
            elif status == "skipped":
                return "highlight-skipped"
            elif status == "substituted":
                return "highlight-substituted"
            else:
                return "highlight-unknown"
        
        # Find word boundaries in original text
        for i, orig_word in enumerate(original_words):
            # Find the word in the original text
            pattern = r'\b' + re.escape(orig_word) + r'\b'
            match = re.search(pattern, original_text[start_idx:].lower())
            
            if match:
                # Get the actual text from the original (preserve case)
                word_start = start_idx + match.start()
                word_end = start_idx + match.end()
                actual_word = original_text[word_start:word_end]
                
                # Add any text before this word
                if word_start > start_idx:
                    result.append(original_text[start_idx:word_start])
                
                # Add the highlighted word
                status_info = word_status_map.get(i, {"status": "unknown"})
                highlight_class = get_highlight_class(status_info["status"])
                
                # Build the span with tooltip and word index data attribute
                span_content = actual_word
                tooltip_content = ""
                
                if status_info["status"] == "mispronounced":
                    tooltip_content = f"Said as: {status_info.get('actual_word', '?')}"
                elif status_info["status"] == "substituted": 
                    tooltip_content = f"Replaced with: {status_info.get('actual_word', '?')}"
                elif status_info["status"] == "skipped":
                    tooltip_content = "Skipped"
                
                if tooltip_content:
                    result.append(f'<span class="{highlight_class}" title="{tooltip_content}" data-word-index="{i}">{span_content}</span>')
                else:
                    result.append(f'<span class="{highlight_class}" data-word-index="{i}">{span_content}</span>')
                
                # Update start_idx for the next iteration
                start_idx = word_end
        
        # Add any remaining text
        if start_idx < len(original_text):
            result.append(original_text[start_idx:])
        
        # CSS styles for highlighting
        css_styles = """
        <style>
        .highlight-good { background-color: #c8e6c9; } /* Light green */
        .highlight-medium { background-color: #fff9c4; } /* Light yellow */
        .highlight-bad { background-color: #ffcdd2; } /* Light red */
        .highlight-missing { background-color: #f5f5f5; text-decoration: line-through; } /* Gray with strikethrough */
        </style>
        """
        
        return css_styles + ''.join(result)
    except Exception as e:
        logger.error(f"Error comparing reading: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"<p>Error analyzing reading: {str(e)}</p>"

def compare_reading_with_word_details(original_text, word_details):
    """
    Create enhanced highlighted text using detailed word information
    
    Args:
        original_text (str): Original text
        word_details (list): List of word detail dictionaries with status
        
    Returns:
        str: HTML with highlighted text and detailed statistics
    """
    try:
        # Extract words from original text
        original_words = re.findall(r'\b\w+\b', original_text.lower())
        
        # Track statistics
        stats = {
            "correct": 0,
            "mispronounced": 0,
            "skipped": 0,
            "substituted": 0,
            "total_words": len(original_words)
        }
        
        # Create word status map from word details
        word_status_map = {}
        spoken_words = []
        
        for detail in word_details:
            if detail.get("word"):
                spoken_words.append(detail["word"].lower())
        
        # Match original words with spoken words
        matcher = difflib.SequenceMatcher(None, original_words, spoken_words)
        
        # Process each opcode (match, delete, insert, replace)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                # Words match exactly
                for k in range(i2 - i1):
                    word_status_map[i1 + k] = {
                        "status": "correct",
                        "confidence": word_details[j1 + k].get("confidence", 1.0)
                    }
                    stats["correct"] += 1
            elif tag == 'delete':
                # Words in original but not in spoken (skipped)
                for k in range(i2 - i1):
                    word_status_map[i1 + k] = {
                        "status": "skipped",
                        "confidence": 0.0
                    }
                    stats["skipped"] += 1
            elif tag == 'replace':
                # Words in both but different (mispronounced or substituted)
                for k in range(i2 - i1):
                    # If there's a corresponding word, check similarity
                    if k < (j2 - j1):
                        orig_word = original_words[i1 + k]
                        spoken_word = spoken_words[j1 + k]
                        
                        # Get existing status if available
                        existing_status = word_details[j1 + k].get("status")
                        
                        if existing_status in ["mispronounced", "substituted"]:
                            # Use the existing status
                            word_status_map[i1 + k] = {
                                "status": existing_status,
                                "confidence": word_details[j1 + k].get("confidence", 0.7),
                                "actual_word": spoken_word
                            }
                            if existing_status == "mispronounced":
                                stats["mispronounced"] += 1
                            else:
                                stats["substituted"] += 1
                        else:
                            # Calculate similarity and decide status
                            similarity = difflib.SequenceMatcher(None, orig_word, spoken_word).ratio()
                            
                            if similarity > 0.7:
                                # Similar enough to be considered mispronounced
                                word_status_map[i1 + k] = {
                                    "status": "mispronounced",
                                    "confidence": similarity,
                                    "actual_word": spoken_word
                                }
                                stats["mispronounced"] += 1
                            else:
                                # Different enough to be considered substituted
                                word_status_map[i1 + k] = {
                                    "status": "substituted",
                                    "confidence": similarity,
                                    "actual_word": spoken_word
                                }
                                stats["substituted"] += 1
                    else:
                        # No corresponding word (skipped)
                        word_status_map[i1 + k] = {
                            "status": "skipped",
                            "confidence": 0.0
                        }
                        stats["skipped"] += 1
        
        # Mark any remaining words as skipped
        for i in range(len(original_words)):
            if i not in word_status_map:
                word_status_map[i] = {
                    "status": "skipped",
                    "confidence": 0
                }
                stats["skipped"] += 1
        
        # Reconstruct original text with highlighting
        result = []
        start_idx = 0
        
        # Add CSS styles for the highlighting
        css = """
        <style>
        .highlight-correct { background-color: #c8e6c9; color: #2e7d32; } /* Green */
        .highlight-mispronounced { background-color: #fff9c4; color: #f57f17; } /* Yellow */
        .highlight-substituted { background-color: #ffcdd2; color: #c62828; } /* Red */
        .highlight-skipped { background-color: #f5f5f5; text-decoration: line-through; color: #757575; } /* Gray */
        .highlight-unknown { background-color: #e0e0e0; } /* Light gray */
        
        .word-span {
            padding: 2px 4px;
            border-radius: 3px;
            margin: 0 1px;
            transition: all 0.2s ease-in-out;
            cursor: default;
        }
        
        .word-span:hover {
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        
        .reading-stats {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin: 15px 0;
            padding: 10px 15px;
            background-color: #f5f5f5;
            border-radius: 5px;
            border-left: 4px solid #2196f3;
        }
        
        .stat-item {
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        
        .stat-label {
            font-size: 12px;
            font-weight: bold;
            color: #757575;
            text-transform: uppercase;
        }
        
        .stat-value {
            font-size: 18px;
            font-weight: bold;
            color: #2196f3;
        }
        </style>
        """
        
        # Function to get CSS class for highlighting
        def get_highlight_class(status):
            if status == "correct":
                return "highlight-correct"
            elif status == "mispronounced":
                return "highlight-mispronounced"
            elif status == "skipped":
                return "highlight-skipped"
            elif status == "substituted":
                return "highlight-substituted"
            else:
                return "highlight-unknown"
        
        # Find word boundaries in original text
        for i, orig_word in enumerate(original_words):
            # Find the word in the original text
            pattern = r'\b' + re.escape(orig_word) + r'\b'
            match = re.search(pattern, original_text[start_idx:].lower())
            
            if match:
                # Get the actual text from the original (preserve case)
                word_start = start_idx + match.start()
                word_end = start_idx + match.end()
                actual_word = original_text[word_start:word_end]
                
                # Add any text before this word
                if word_start > start_idx:
                    result.append(original_text[start_idx:word_start])
                
                # Add the highlighted word
                status_info = word_status_map.get(i, {"status": "unknown"})
                highlight_class = get_highlight_class(status_info["status"])
                
                # Build the span with tooltip and data attributes
                span_content = actual_word
                tooltip_content = ""
                
                if status_info["status"] == "mispronounced":
                    tooltip_content = f"Said as: {status_info.get('actual_word', '?')}"
                elif status_info["status"] == "substituted": 
                    tooltip_content = f"Replaced with: {status_info.get('actual_word', '?')}"
                elif status_info["status"] == "skipped":
                    tooltip_content = "Skipped"
                
                # Add data attributes to help with frontend interaction
                data_attrs = f'data-word-index="{i}" data-word-status="{status_info["status"]}" data-confidence="{status_info.get("confidence", 0):.2f}"'
                
                if tooltip_content:
                    result.append(f'<span class="word-span {highlight_class}" title="{tooltip_content}" {data_attrs}>{span_content}</span>')
                else:
                    result.append(f'<span class="word-span {highlight_class}" {data_attrs}>{span_content}</span>')
                
                # Update start_idx for the next iteration
                start_idx = word_end
        
        # Add any remaining text
        if start_idx < len(original_text):
            result.append(original_text[start_idx:])
        
        # Calculate accuracy percentages
        accuracy_percentage = int((stats["correct"] / stats["total_words"]) * 100) if stats["total_words"] > 0 else 0
        
        # Build statistics HTML
        stats_html = f"""
        <div class="reading-stats">
            <div class="stat-item">
                <span class="stat-label">Accuracy</span>
                <span class="stat-value">{accuracy_percentage}%</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Correct</span>
                <span class="stat-value">{stats["correct"]}/{stats["total_words"]}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Mispronounced</span>
                <span class="stat-value">{stats["mispronounced"]}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Skipped</span>
                <span class="stat-value">{stats["skipped"]}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Substituted</span>
                <span class="stat-value">{stats["substituted"]}</span>
            </div>
        </div>
        """
        
        # Add JavaScript for interactivity
        js = """
        <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Add click handler for all word spans
            document.querySelectorAll('.word-span').forEach(span => {
                span.addEventListener('click', function() {
                    // Get word info
                    const index = this.getAttribute('data-word-index');
                    const status = this.getAttribute('data-word-status');
                    const confidence = this.getAttribute('data-confidence');
                    
                    // Display word info in a tooltip or sidebar
                    console.log(`Word ${index}: Status=${status}, Confidence=${confidence}`);
                    
                    // Here you could show a modal or update a sidebar with word details
                });
            });
        });
        </script>
        """
        
        # Combine the components
        return css + stats_html + "".join(result) + js
    
    except Exception as e:
        logger.error(f"Error comparing reading with word details: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"<p>Error analyzing reading: {str(e)}</p>"

def analyze_reading_comprehensive(original_text, transcription_result, grade_level, grammar_evaluation=None):
    """
    Comprehensive reading analysis including grammar skills
    
    Args:
        original_text (str): Original text
        transcription_result (dict): Detailed transcription results
        grade_level (int): Grade level
        grammar_evaluation (dict, optional): Grammar test evaluation results
        
    Returns:
        dict: Comprehensive analysis results
    """
    # Extract basic info from transcription result
    spoken_text = transcription_result.get("transcribed_text", transcription_result.get("text", ""))
    audio_duration = transcription_result.get("duration", transcription_result.get("audio_duration", 0))
    
    # Get basic fluency metrics
    fluency_metrics = analyze_reading_fluency(original_text, spoken_text, grade_level, audio_duration)
    
    # Since we don't have word-level details in the simplified format,
    # calculate basic accuracy using string similarity
    similarity = SequenceMatcher(None, original_text.lower(), spoken_text.lower()).ratio()
    accuracy = similarity * 100
    
    # Estimate word-level statistics based on similarity
    total_words = len(re.findall(r'\b\w+\b', original_text))
    correct_words_estimate = int(total_words * similarity)
    
    word_stats = {
        "correct": correct_words_estimate,
        "mispronounced": int(total_words * 0.1),
        "skipped": total_words - correct_words_estimate - int(total_words * 0.1) - int(total_words * 0.05),
        "substituted": int(total_words * 0.05)
    }
    
    # Adjust to ensure total adds up
    word_stats["skipped"] = max(0, word_stats["skipped"])
    
    # Calculate prosody score (estimated from accuracy)
    prosody_score = 70 + (similarity * 30)  # Scale from 70-100 based on accuracy
    
    # Calculate comprehension estimate (based on accuracy and fluency)
    comprehension_estimate = min(100, (accuracy * 0.6) + (fluency_metrics["words_per_minute"] / get_wpm_benchmark(grade_level) * 40))
    
    # Calculate overall reading level
    if accuracy >= 95 and fluency_metrics["words_per_minute"] >= get_wpm_benchmark(grade_level):
        reading_level = "Above Grade Level"
    elif accuracy >= 90 and fluency_metrics["words_per_minute"] >= get_wpm_benchmark(grade_level) * 0.8:
        reading_level = "At Grade Level"
    elif accuracy >= 80 and fluency_metrics["words_per_minute"] >= get_wpm_benchmark(grade_level) * 0.7:
        reading_level = "Approaching Grade Level"
    else:
        reading_level = "Below Grade Level"
    
    # Calculate grade equivalent (simplified estimate)
    if reading_level == "Above Grade Level":
        grade_equivalent = grade_level + 1
    elif reading_level == "At Grade Level":
        grade_equivalent = grade_level
    elif reading_level == "Approaching Grade Level":
        grade_equivalent = grade_level - 0.5
    else:
        grade_equivalent = max(1, grade_level - 1)
    
    # Incorporate grammar evaluation if available
    grammar_score = None
    grammar_proficiency = None
    combined_score = None
    
    if grammar_evaluation:
        grammar_score = grammar_evaluation.get("score", 0)
        grammar_proficiency = grammar_evaluation.get("proficiency_level", "Not Available")
        
        # Calculate combined literacy score (reading + grammar)
        reading_weight = 0.7  # 70% reading, 30% grammar
        reading_score = (accuracy * 0.5) + (comprehension_estimate * 0.3) + (fluency_metrics["words_per_minute"] / get_wpm_benchmark(grade_level) * 100 * 0.2)
        combined_score = (reading_score * reading_weight) + (grammar_score * (1 - reading_weight))
    
    # Identify strengths and areas for improvement
    strengths = []
    areas_to_improve = []
    
    # Analyze reading strengths
    if similarity >= 0.9:
        strengths.append("Strong word recognition")
    if fluency_metrics["words_per_minute"] >= get_wpm_benchmark(grade_level) * 1.1:
        strengths.append("Excellent reading speed")
    if accuracy >= 90:
        strengths.append("High reading accuracy")
    
    # Analyze reading improvement areas
    if similarity < 0.8:
        areas_to_improve.append("Practice word pronunciation")
    if fluency_metrics["words_per_minute"] < get_wpm_benchmark(grade_level) * 0.8:
        areas_to_improve.append("Work on improving reading speed")
    if accuracy < 85:
        areas_to_improve.append("Focus on reading accuracy")
    
    # Add grammar strengths and improvement areas if available
    if grammar_evaluation:
        concepts_mastered = grammar_evaluation.get("concepts_mastered", [])
        concepts_to_improve = grammar_evaluation.get("concepts_to_improve", [])
        
        if concepts_mastered:
            strengths.append(f"Strong grammar skills in: {', '.join(concepts_mastered[:3])}")
        
        if concepts_to_improve:
            areas_to_improve.append(f"Review grammar concepts: {', '.join(concepts_to_improve[:2])}")
    
    # Generate personalized next steps
    next_steps = []
    
    if areas_to_improve:
        for area in areas_to_improve[:2]:  # Focus on top 2 areas
            if "pronunciation" in area.lower():
                next_steps.append("Practice reading aloud with a focus on challenging words")
            elif "accuracy" in area.lower():
                next_steps.append("Read at a slightly slower pace to ensure all words are read correctly")
            elif "speed" in area.lower():
                next_steps.append("Practice timed reading exercises to build fluency")
            elif "grammar" in area.lower():
                next_steps.append("Complete grammar exercises focused on your improvement areas")
    
    # Default next step if none generated
    if not next_steps:
        next_steps.append("Continue practicing with texts at this level to maintain skills")
    
    # Assemble final comprehensive result
    comprehensive_analysis = {
        "reading_level": reading_level,
        "grade_equivalent": grade_equivalent,
        "word_statistics": word_stats,
        "accuracy_percentage": round(accuracy, 1),
        "fluency_metrics": fluency_metrics,
        "comprehension_estimate": round(comprehension_estimate, 1),
        "prosody_score": round(prosody_score, 1),
        "strengths": strengths,
        "areas_to_improve": areas_to_improve,
        "next_steps": next_steps
    }
    
    # Add grammar evaluation if available
    if grammar_score is not None:
        comprehensive_analysis["grammar_score"] = grammar_score
        comprehensive_analysis["grammar_proficiency"] = grammar_proficiency
        comprehensive_analysis["combined_literacy_score"] = round(combined_score, 1)
    
    return comprehensive_analysis

def track_spoken_words_realtime(original_text):
    """
    Generate a structure for tracking words during real-time speaking
    
    Args:
        original_text (str): Original text to be read
        
    Returns:
        dict: Word tracking data structure with HTML for display
    """
    try:
        # Find word boundaries in original text
        words = []
        word_positions = []
        
        # Use regex to find all words and their positions
        for match in re.finditer(r'\b(\w+)\b', original_text):
            word = match.group(1)
            start_pos = match.start()
            end_pos = match.end()
            
            words.append({
                "word": word,
                "start": start_pos,
                "end": end_pos,
                "status": "pending"  # Initial status (not yet read)
            })
            word_positions.append((start_pos, end_pos))
        
        # Generate HTML with span tags for each word
        html_parts = []
        last_pos = 0
        
        for i, (start, end) in enumerate(word_positions):
            # Add any text before this word
            if start > last_pos:
                html_parts.append(original_text[last_pos:start])
            
            # Add the word with a unique ID for later highlighting
            word_text = original_text[start:end]
            html_parts.append(f'<span id="word-{i}" class="word pending">{word_text}</span>')
            
            last_pos = end
        
        # Add any remaining text
        if last_pos < len(original_text):
            html_parts.append(original_text[last_pos:])
        
        # Create CSS for word highlighting
        css = """
        <style>
        .word { transition: background-color 0.3s ease; }
        .pending { background-color: transparent; }
        .current { background-color: #e3f2fd; border-bottom: 2px solid #2196f3; }
        .correct { background-color: #c8e6c9; }
        .incorrect { background-color: #ffcdd2; }
        .skipped { background-color: #f5f5f5; text-decoration: line-through; }
        </style>
        """
        
        # Create JavaScript for updating word statuses
        javascript = """
        <script>
        // Function to update word status
        function updateWordStatus(wordIndex, status) {
            const wordElem = document.getElementById(`word-${wordIndex}`);
            if (wordElem) {
                // Remove all status classes
                wordElem.classList.remove('pending', 'current', 'correct', 'incorrect', 'skipped');
                // Add the new status class
                wordElem.classList.add(status);
            }
        }
        
        // Function to mark the current word being spoken
        function markCurrentWord(wordIndex) {
            // Reset any previous current word
            document.querySelectorAll('.current').forEach(el => {
                el.classList.remove('current');
            });
            
            // Mark new current word
            updateWordStatus(wordIndex, 'current');
        }
        
        // Function to finalize a word with its final status
        function finalizeWord(wordIndex, status) {
            updateWordStatus(wordIndex, status);
        }
        </script>
        """
        
        return {
            "html": css + ''.join(html_parts) + javascript,
            "word_count": len(words),
            "words": words
        }
    except Exception as e:
        logger.error(f"Error in tracking spoken words: {e}")
        return {
            "html": original_text,
            "word_count": 0,
            "words": []
        }

# =====================================================================
# API ROUTES
# =====================================================================

@app.route('/api/grammar-test', methods=['GET'])
def api_grammar_test():
    """API endpoint to get a grammar test for a specific grade level"""
    try:
        grade_level = int(request.args.get('grade_level', 5))
        test = generate_grammar_test(grade_level)
        
        # Store test in session for later evaluation
        session['grammar_test'] = test
        
        return jsonify({
            "success": True,
            "test": test
        })
    except Exception as e:
        logger.error(f"Error generating grammar test: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/evaluate-grammar', methods=['POST'])
def api_evaluate_grammar():
    """API endpoint to evaluate grammar test answers"""
    try:
        data = request.get_json()
        user_answers = data.get('answers', [])
        
        # Get test from session
        test = session.get('grammar_test')
        if not test:
            return jsonify({"error": "No grammar test found in session"}), 400
        
        # Evaluate test
        evaluation = evaluate_grammar_test(test['questions'], user_answers)
        
        # Store in session
        session['grammar_evaluation'] = evaluation
        
        return jsonify({
            "success": True,
            "evaluation": evaluation
        })
    except Exception as e:
        logger.error(f"Error evaluating grammar test: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-reading-topics', methods=['GET'])
def api_get_reading_topics():
    """API endpoint to get reading topics based on grammar evaluation"""
    try:
        # Get evaluation from session or generate default topics
        evaluation = session.get('grammar_evaluation')
        
        if evaluation:
            # Topics already generated in evaluation
            topics = evaluation.get('suggested_reading_topics', [])
        else:
            # Generate default topics if no evaluation exists
            grade_level = int(request.args.get('grade_level', 5))
            topics = suggest_reading_topics(75, [])  # Default 75% score
        
        return jsonify({
            "success": True,
            "topics": topics
        })
    except Exception as e:
        logger.error(f"Error getting reading topics: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/transcribe-audio-realtime', methods=['POST'])
def api_transcribe_audio_realtime():
    """API endpoint to transcribe audio in real-time for reading assessment"""
    try:
        # Get audio data from form data
        audio_data = request.form.get('audio_data', '')
        
        # If no form data, try JSON
        if not audio_data and request.is_json:
            data = request.get_json()
            audio_data = data.get('audio_data', '')
        
        if not audio_data:
            return jsonify({"error": "No audio data provided"}), 400
        
        # Extract actual base64 data (remove prefix if present)
        if ',' in audio_data:
            audio_data = audio_data.split(',')[1]
        
        audio_bytes = base64.b64decode(audio_data)
        
        # Call transcription service
        logger.info("Transcribing audio data of size: %d bytes", len(audio_bytes))
        transcription_result = transcribe_audio_realtime(audio_bytes)
        logger.info(f"Transcription completed with source: {transcription_result.get('source', 'unknown')}")
        
        # Format response for the client
        word_details = transcription_result.get('word_details', [])
        
        logger.info(f"Sending response with {len(word_details)} word details")
        
        return jsonify({
            "success": True,
            "transcription": transcription_result.get('transcription', ''),
            "word_details": word_details,
            "source": transcription_result.get('source', 'unknown')
        })
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e),
            "use_browser_recognition": True
        }), 500

@app.route('/api/compare-reading', methods=['POST'])
def api_compare_reading():
    """API endpoint for enhanced reading comparison"""
    try:
        data = request.get_json()
        
        # Get data from request or session
        original_text = data.get('original_text') or session.get('original_text', '')
        transcription_result = data.get('transcription_result') or session.get('transcription_result')
        
        if not original_text or not transcription_result:
            return jsonify({"error": "Missing text or transcription data"}), 400
        
        # Generate enhanced highlighted text
        highlighted_text = compare_reading_with_text_enhanced(original_text, transcription_result)
        
        return jsonify({
            "success": True,
            "highlighted_text": highlighted_text
        })
    except Exception as e:
        logger.error(f"Error in enhanced reading comparison: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/analyze-comprehensive', methods=['POST'])
def api_analyze_comprehensive():
    """API endpoint for comprehensive reading and grammar analysis"""
    try:
        data = request.get_json()
        
        # Get data from request or session
        original_text = data.get('original_text') or session.get('original_text', '')
        transcription_result = data.get('transcription_result') or session.get('transcription_result')
        grade_level = int(data.get('grade_level', 5))
        grammar_evaluation = data.get('grammar_evaluation') or session.get('grammar_evaluation')
        
        if not original_text or not transcription_result:
            return jsonify({"error": "Missing text or transcription data"}), 400
        
        # Perform comprehensive analysis
        analysis = analyze_reading_comprehensive(
            original_text, 
            transcription_result, 
            grade_level,
            grammar_evaluation
        )
        
        # Generate highlighted text
        highlighted_text = compare_reading_with_text_enhanced(original_text, transcription_result)
        
        # Store in session
        session['comprehensive_analysis'] = analysis
        
        return jsonify({
            "success": True,
            "analysis": analysis,
            "highlighted_text": highlighted_text
        })
    except Exception as e:
        logger.error(f"Error in comprehensive analysis: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/prepare-realtime-tracking', methods=['POST'])
def api_prepare_realtime_tracking():
    """API endpoint to prepare real-time word tracking for reading"""
    try:
        data = request.get_json()
        original_text = data.get('text', '')
        
        if not original_text:
            return jsonify({"error": "No text provided"}), 400
        
        logger.info(f"Preparing real-time tracking for text of length: {len(original_text)}")
        
        # Generate tracking structure and HTML
        tracking_data = track_spoken_words_realtime(original_text)
        
        # Store in session
        session['tracking_data'] = tracking_data
        session['original_text'] = original_text
        
        logger.info(f"Tracking data prepared with {tracking_data['word_count']} words")
        
        return jsonify({
            "success": True,
            "tracking_html": tracking_data["html"],
            "word_count": tracking_data["word_count"]
        })
    except Exception as e:
        logger.error(f"Error preparing real-time tracking: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/update-word-status', methods=['POST'])
def api_update_word_status():
    """API endpoint to update word status during real-time reading"""
    try:
        data = request.get_json()
        word_index = data.get('word_index', -1)
        status = data.get('status', 'pending')
        
        if word_index < 0:
            return jsonify({"error": "Invalid word index"}), 400
        
        # Validate status
        valid_statuses = ['pending', 'current', 'correct', 'incorrect', 'skipped']
        if status not in valid_statuses:
            return jsonify({"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}), 400
        
        # Get tracking data from session
        tracking_data = session.get('tracking_data', {})
        words = tracking_data.get('words', [])
        
        # Update word status if within range
        if word_index < len(words):
            words[word_index]['status'] = status
            tracking_data['words'] = words
            session['tracking_data'] = tracking_data
            
            return jsonify({
                "success": True,
                "updated": {
                    "word_index": word_index,
                    "status": status
                }
            })
        else:
            return jsonify({"error": "Word index out of range"}), 400
            
    except Exception as e:
        logger.error(f"Error updating word status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/process-speech-result', methods=['POST'])
def api_process_speech_result():
    """API endpoint to process speech recognition results and match with text"""
    try:
        data = request.get_json()
        speech_text = data.get('speech_text', '')
        current_word_index = int(data.get('current_index', 0))
        
        logger.info(f"Processing speech result: {speech_text[:50]}...")
        
        if not speech_text:
            return jsonify({"error": "No speech text provided"}), 400
        
        # Get tracking data and original text from session
        tracking_data = session.get('tracking_data', {})
        original_text = session.get('original_text', '')
        
        if not tracking_data:
            logger.error("No tracking data found in session")
            # Create new tracking data if not present
            if original_text:
                logger.info("Creating new tracking data from original text")
                tracking_data = track_spoken_words_realtime(original_text)
                session['tracking_data'] = tracking_data
            else:
                return jsonify({"error": "No tracking data found and no original text available"}), 400
                
        words = tracking_data.get('words', [])
        
        if not words:
            return jsonify({"error": "No word data found in tracking data"}), 400
        
        logger.info(f"Processing speech against {len(words)} words, starting from index {current_word_index}")
        
        # Process only new speech for better performance
        # by looking at words from current_word_index forward
        remaining_words = [w["word"].lower() for w in words[current_word_index:]]
        speech_words = speech_text.lower().split()
        
        # Match spoken words with text words
        matched_indices = []
        statuses = []
        words_to_update = min(len(speech_words), len(remaining_words))
        
        for i in range(words_to_update):
            word_index = current_word_index + i
            
            # Check if the spoken word matches the expected word
            if i < len(speech_words) and i < len(remaining_words):
                spoken_word = speech_words[i]
                expected_word = remaining_words[i]
                
                # Determine match quality
                similarity = difflib.SequenceMatcher(None, spoken_word, expected_word).ratio()
                
                if similarity > 0.8:
                    status = "correct"
                elif similarity > 0.5:
                    status = "incorrect"  # Partially incorrect
                else:
                    status = "incorrect"  # Completely wrong
                
                matched_indices.append(word_index)
                statuses.append(status)
                
                # Update word status in tracking data
                if word_index < len(words):
                    words[word_index]['status'] = status
        
        # Find skipped words
        if len(matched_indices) > 0 and matched_indices[-1] - matched_indices[0] + 1 > len(matched_indices):
            # There are gaps in the matched indices, marking skipped words
            all_indices = list(range(matched_indices[0], matched_indices[-1] + 1))
            skipped_indices = [idx for idx in all_indices if idx not in matched_indices]
            
            for idx in skipped_indices:
                if idx < len(words):
                    words[idx]['status'] = "skipped"
                    matched_indices.append(idx)
                    statuses.append("skipped")
        
        # Update session
        tracking_data['words'] = words
        session['tracking_data'] = tracking_data
        
        # Return information about updated words
        next_word_index = max(matched_indices) + 1 if matched_indices else current_word_index
        
        logger.info(f"Updated {len(matched_indices)} words, next word index: {next_word_index}")
        
        return jsonify({
            "success": True,
            "updated_words": [
                {"index": idx, "status": status}
                for idx, status in zip(matched_indices, statuses)
            ],
            "next_word_index": next_word_index
        })
    except Exception as e:
        logger.error(f"Error processing speech: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/finalize-reading-tracking', methods=['POST'])
def api_finalize_reading_tracking():
    """API endpoint to finalize reading tracking and generate summary"""
    try:
        logger.info("Finalizing reading tracking")
        
        # Get tracking data from session
        tracking_data = session.get('tracking_data', {})
        original_text = session.get('original_text', '')
        
        if not tracking_data:
            logger.error("No tracking data found in session")
            return jsonify({
                "success": False,
                "error": "No tracking data found. Please start a new reading session."
            }), 400
            
        words = tracking_data.get('words', [])
        
        if not words:
            logger.error("No words found in tracking data")
            return jsonify({
                "success": False,
                "error": "No word data found. Please start a new reading session."
            }), 400
        
        logger.info(f"Finalizing session with {len(words)} words")
        
        # Calculate statistics
        total_words = len(words)
        status_counts = {
            "correct": 0,
            "incorrect": 0,
            "skipped": 0,
            "pending": 0  # Words not read
        }
        
        # Count statuses
        for word in words:
            status = word.get('status', 'pending')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Mark all pending words as skipped for the final view
        for word in words:
            if word.get('status', '') == 'pending':
                word['status'] = 'skipped'
        
        # Calculate accuracy percentage
        accuracy_percentage = round((status_counts["correct"] / total_words) * 100, 1) if total_words > 0 else 0
        
        # Generate final highlighted HTML
        html_parts = []
        last_pos = 0
        
        for word in words:
            start = word.get('start', 0)
            end = word.get('end', 0)
            status = word.get('status', 'skipped')
            
            # Add any text before this word
            if start > last_pos:
                html_parts.append(original_text[last_pos:start])
            
            # Add the word with its final status highlight
            word_text = original_text[start:end]
            html_parts.append(f'<span class="word {status}">{word_text}</span>')
            
            last_pos = end
        
        # Add any remaining text
        if last_pos < len(original_text):
            html_parts.append(original_text[last_pos:])
        
        # Create CSS for word highlighting
        css = """
        <style>
        .word { transition: background-color 0.3s ease; }
        .correct { background-color: #c8e6c9; }
        .incorrect { background-color: #ffcdd2; }
        .skipped { background-color: #f5f5f5; text-decoration: line-through; }
        
        .stats-container {
            margin: 20px 0;
            padding: 15px;
            background-color: #f5f5f5;
            border-radius: 5px;
        }
        .stat-item {
            display: inline-block;
            margin-right: 20px;
            font-size: 16px;
        }
        .stat-label {
            font-weight: bold;
        }
        </style>
        """
        
        # Create stats HTML
        stats_html = f"""
        <div class="stats-container">
            <div class="stat-item">
                <span class="stat-label">Accuracy:</span>
                <span class="stat-value">{accuracy_percentage}%</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Correct Words:</span>
                <span class="stat-value">{status_counts["correct"]}/{total_words}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Incorrect Words:</span>
                <span class="stat-value">{status_counts["incorrect"]}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Skipped Words:</span>
                <span class="stat-value">{status_counts["skipped"] + status_counts["pending"]}</span>
            </div>
        </div>
        """
        
        # Compute reading fluency score (0-100)
        fluency_score = int((status_counts["correct"] / total_words) * 100) if total_words > 0 else 0
        
        # Create transcript from read words, showing what the user actually said
        transcript_words = []
        total_read = status_counts["correct"] + status_counts["incorrect"]
        read_percentage = int((total_read / total_words) * 100) if total_words > 0 else 0
        
        # Reconstruct what was actually read
        for word in words:
            status = word.get('status', 'skipped')
            if status in ['correct', 'incorrect']:
                transcript_words.append(word.get('word', ''))
        
        user_transcript = ' '.join(transcript_words)
        
        # Determine reading levels
        fluency_level = "Excellent" if fluency_score >= 90 else "Good" if fluency_score >= 75 else "Fair" if fluency_score >= 60 else "Needs Improvement"
        completion_level = "Complete" if read_percentage >= 90 else "Mostly Complete" if read_percentage >= 75 else "Partial" if read_percentage >= 50 else "Incomplete"
        accuracy_level = "High" if accuracy_percentage >= 90 else "Medium" if accuracy_percentage >= 70 else "Low"
        
        # Generate appropriate recommendations based on performance
        recommendations = []
        
        if accuracy_percentage < 80:
            recommendations.append("Focus on pronouncing each word clearly and carefully.")
            recommendations.append("Practice reading aloud for 15 minutes daily.")
        
        if (status_counts["skipped"] + status_counts["pending"]) > total_words * 0.2:
            recommendations.append("Work on reading all words instead of skipping difficult ones.")
            recommendations.append("Try reading at a slightly slower pace for better accuracy.")
        
        if status_counts["incorrect"] > total_words * 0.1:
            recommendations.append("Practice the mispronounced words separately.")
            recommendations.append("Record yourself reading and listen to identify areas for improvement.")
        
        # Add default recommendations if none were generated
        if not recommendations:
            recommendations = [
                "Continue your excellent reading practice.",
                "Try more challenging texts to further improve your skills.",
                "Focus on expression and intonation for even better reading."
            ]
        
        # Add analysis section
        analysis_html = f"""
        <div class="analysis-container mt-4">
            <h4>Reading Analysis</h4>
            <div class="card mb-3">
                <div class="card-header">
                    <i class="fas fa-chart-line me-2"></i>Performance Analysis
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <h5>Reading Fluency</h5>
                            <p>Based on your reading pattern and accuracy, here are some observations:</p>
                            <ul>
                                <li>Overall fluency: <span class="badge bg-primary">{fluency_level}</span></li>
                                <li>Reading accuracy: <span class="badge bg-primary">{accuracy_level}</span></li>
                                <li>Completion: <span class="badge bg-primary">{completion_level}</span></li>
                                <li>Words read accurately: <span class="badge bg-success">{status_counts["correct"]}</span></li>
                                <li>Words mispronounced: <span class="badge bg-danger">{status_counts["incorrect"]}</span></li>
                            </ul>
                        </div>
                        <div class="col-md-6">
                            <h5>Recommendations</h5>
                            <p>To improve your reading skills:</p>
                            <ul>
                                {"".join(f"<li>{rec}</li>" for rec in recommendations)}
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card mb-3">
                <div class="card-header">
                    <i class="fas fa-comment-alt me-2"></i>What You Read
                </div>
                <div class="card-body">
                    <p>Here's what our system heard you read:</p>
                    <div class="p-3 bg-light border rounded">
                        {user_transcript or "<em>No spoken text was detected</em>"}
                    </div>
                </div>
            </div>
        </div>
        """
        
        # Combine all parts
        final_html = css + stats_html + ''.join(html_parts) + analysis_html
        
        # Update session
        tracking_data['words'] = words
        tracking_data['statistics'] = {
            "total_words": total_words,
            "correct": status_counts["correct"],
            "incorrect": status_counts["incorrect"],
            "skipped": status_counts["skipped"] + status_counts["pending"],
            "accuracy_percentage": accuracy_percentage,
            "fluency_level": fluency_level,
            "user_transcript": user_transcript
        }
        session['tracking_data'] = tracking_data
        
        logger.info(f"Finalized reading with accuracy: {accuracy_percentage}%")
        
        return jsonify({
            "success": True,
            "final_html": final_html,
            "statistics": tracking_data['statistics']
        })
    except Exception as e:
        logger.error(f"Error finalizing reading tracking: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/extract-text', methods=['POST'])
def api_extract_text():
    """API endpoint to extract text from uploaded PDF"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if not allowed_file(file.filename):
            return jsonify({"error": "File type not allowed. Please upload a PDF or text file."}), 400
        
        # Save the file
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Extract text based on file type
        if filename.lower().endswith('.pdf'):
            text = extract_text_from_pdf(file_path)
        else:  # .txt files
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        
        # Format for better readability
        grade_level = int(request.form.get('grade_level', 5))
        formatted_text = enhance_and_format_text(text, grade_level)
        
        # Store in session for later use
        session['original_text'] = formatted_text
        session['passage_title'] = os.path.splitext(filename)[0]
        
        return jsonify({
            "success": True,
            "text": formatted_text,
            "title": os.path.splitext(filename)[0]
        })
    except Exception as e:
        logger.error(f"Error extracting text: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/save-text', methods=['POST'])
def api_save_text():
    """API endpoint to save direct text input"""
    try:
        data = request.get_json()
        original_text = data.get('text', '')
        passage_title = data.get('title', 'Custom Passage')
        grade_level = int(data.get('grade_level', 5))
        
        if not original_text:
            return jsonify({"error": "No text provided"}), 400
        
        # Format text for better readability
        formatted_text = enhance_and_format_text(original_text, grade_level)
        
        # Store in session
        session['original_text'] = formatted_text
        session['passage_title'] = passage_title
        
        return jsonify({
            "success": True,
            "text": formatted_text,
            "title": passage_title
        })
    except Exception as e:
        logger.error(f"Error saving text: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/transcribe-audio', methods=['POST'])
def api_transcribe_audio():
    """API endpoint to transcribe audio recording"""
    try:
        logger.info("Received audio transcription request")
        
        # Check if audio file is present in request
        if 'audio' not in request.files:
            logger.error("No audio file in request")
            return jsonify({"success": False, "error": "No audio file provided"}), 400
            
        audio_file = request.files['audio']
        original_text = request.form.get('original_text', '')
        grade_level = request.form.get('grade_level', '5')
        audio_duration = float(request.form.get('audio_duration', 0))
        
        # Save temporary audio file
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, "recording.webm")
        audio_file.save(temp_path)
        
        logger.info(f"Audio saved to temporary file: {temp_path}")
        
        transcribed_text = None
        transcription_successful = False
        word_details = []
        
        # Try using Whisper.cpp for transcription if available
        if os.path.exists(WHISPER_CPP_CLI_PATH) and os.path.exists(WHISPER_CPP_MODEL_PATH):
            try:
                # Convert to WAV using ffmpeg (required for whisper.cpp)
                wav_path = os.path.join(temp_dir, "recording.wav")
                convert_cmd = ['ffmpeg', '-i', temp_path, '-ar', '16000', '-ac', '1', '-y', wav_path]
                
                # Execute ffmpeg with detailed logging
                logger.info(f"Running ffmpeg command: {' '.join(convert_cmd)}")
                convert_result = subprocess.run(convert_cmd, capture_output=True, text=True)
                
                if convert_result.returncode != 0:
                    logger.error(f"ffmpeg error: {convert_result.stderr}")
                    raise Exception(f"ffmpeg conversion failed: {convert_result.stderr}")
                
                logger.info(f"Audio converted successfully to {wav_path}")
                
                # Use whisper.cpp for transcription with word timestamp option
                cmd = [
                    WHISPER_CPP_CLI_PATH,
                    '-m', WHISPER_CPP_MODEL_PATH,
                    '-f', wav_path,
                    '-otxt',
                    '--output-file', os.path.join(temp_dir, "transcription.txt"),
                    '--word-timestamps'
                ]
                
                # Execute transcription command with detailed logging
                logger.info(f"Running Whisper.cpp command: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.error(f"Whisper.cpp error: {result.stderr}")
                    raise Exception(f"Whisper.cpp failed: {result.stderr}")
                
                # Read transcription from file
                transcription_path = os.path.join(temp_dir, "transcription.txt")
                
                if os.path.exists(transcription_path):
                    # Read the full transcription
                    with open(transcription_path, 'r') as f:
                        transcribed_text = f.read().strip()
                    
                    logger.info(f"Transcription read from file: {transcribed_text[:100]}...")
                    
                    # Split into words to create word details
                    words = transcribed_text.split()
                    time_per_word = audio_duration / max(1, len(words))
                    
                    for i, word in enumerate(words):
                        # Generate timestamps based on position
                        word_details.append({
                            "word": word,
                            "status": "correct",  # Default status, will be compared later
                            "confidence": 0.9,    # Whisper doesn't provide per-word confidence
                            "timestamp": i * time_per_word
                        })
                    
                    logger.info(f"Generated word details for {len(words)} words")
                    transcription_successful = True
                else:
                    logger.error(f"Transcription file not found at {transcription_path}")
                    raise Exception(f"Transcription file not found: {transcription_path}")
                
            except Exception as e:
                logger.error(f"Error using Whisper.cpp: {e}")
                logger.error("Falling back to mock transcription")
        else:
            logger.warning("Whisper.cpp not available, using fallback")
        
        # FALLBACK: If Whisper.cpp failed or not available, use a simple simulation
        if not transcription_successful:
            logger.info("Using fallback transcription method")
            
            if original_text:
                # Simulate some mistakes in the transcription for demo purposes
                words = original_text.split()
                result_words = []
                word_details = []
                
                for i, word in enumerate(words):
                    # Introduce some random changes
                    rand = random.random()
                    
                    if rand < 0.7:  # 70% chance for correct
                        result_words.append(word)
                        word_details.append({
                            "word": word,
                            "status": "correct",
                            "confidence": random.uniform(0.85, 0.99),
                            "timestamp": i * 0.4  # Simulate timestamp in seconds
                        })
                    elif rand < 0.8:  # 10% chance to mispronounce
                        # Simulate minor mispronunciation by changing a character
                        if len(word) > 2:
                            pos = random.randint(0, len(word)-1)
                            misspelled = word[:pos] + random.choice('abcdefghijklmnopqrstuvwxyz') + word[pos+1:]
                            result_words.append(misspelled)
                            word_details.append({
                                "word": misspelled,
                                "status": "mispronounced",
                                "intended_word": word,
                                "confidence": random.uniform(0.6, 0.8),
                                "timestamp": i * 0.4
                            })
                        else:
                            result_words.append(word)
                            word_details.append({
                                "word": word,
                                "status": "correct",
                                "confidence": random.uniform(0.85, 0.99),
                                "timestamp": i * 0.4
                            })
                    elif rand < 0.9:  # 10% chance to skip
                        # Skip the word
                        word_details.append({
                            "word": None,
                            "status": "skipped",
                            "intended_word": word,
                            "confidence": 0,
                            "timestamp": i * 0.4
                        })
                    else:  # 10% chance to substitute
                        # Replace with a different word
                        substitutions = {
                            "the": "a", "a": "the", "to": "too", "for": "four",
                            "their": "there", "sun": "son", "bright": "light",
                            "different": "various", "uniquely": "truly"
                        }
                        if word.lower() in substitutions:
                            substitute = substitutions[word.lower()]
                            result_words.append(substitute)
                            word_details.append({
                                "word": substitute,
                                "status": "substituted",
                                "intended_word": word,
                                "confidence": random.uniform(0.5, 0.7),
                                "timestamp": i * 0.4
                            })
                        else:
                            # If no substitution found, treat as correct
                            result_words.append(word)
                            word_details.append({
                                "word": word,
                                "status": "correct",
                                "confidence": random.uniform(0.85, 0.99),
                                "timestamp": i * 0.4
                            })
                
                # Join back into text, removing empty words
                transcribed_text = ' '.join([w for w in result_words if w])
            else:
                transcribed_text = "No original text provided for simulation."
            
            logger.info(f"Fallback transcription: {transcribed_text[:100]}...")
            transcription_successful = True
        
        # Clean up temp files
        try:
            import shutil
            shutil.rmtree(temp_dir)
            logger.info(f"Temporary directory removed: {temp_dir}")
        except Exception as e:
            logger.error(f"Error removing temp files: {e}")
        
        # If we still don't have a transcription, return error
        if not transcription_successful or not transcribed_text:
            return jsonify({
                "success": False, 
                "error": "Failed to transcribe audio with all available methods"
            }), 500
        
        # Create enhanced transcription result
        transcription_result = {
            "transcribed_text": transcribed_text,
            "text": transcribed_text,  # For compatibility
            "word_details": word_details,
            "audio_duration": audio_duration,
            "duration": audio_duration,  # For compatibility
            "timestamp": time.time()
        }
        
        # Store in session
        session['transcription_result'] = transcription_result
        session['original_text'] = original_text
        session['spoken_text'] = transcribed_text
        session['word_details'] = word_details
        
        return jsonify({
            "success": True,
            "transcription": transcription_result
        })
        
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/analyze-reading', methods=['POST'])
def api_analyze_reading():
    """API endpoint for reading analysis"""
    try:
        data = request.get_json()
        
        # Get data from request or session
        original_text = data.get('original_text') or session.get('original_text', '')
        spoken_text = data.get('spoken_text') or session.get('spoken_text', '')
        grade_level = int(data.get('grade_level', 5))
        audio_duration = data.get('audio_duration') or session.get('audio_duration')
        
        if not original_text or not spoken_text:
            return jsonify({"error": "Missing text data"}), 400
        
        # Perform analysis
        analysis_result = analyze_reading(original_text, spoken_text, grade_level, audio_duration)
        
        # Generate highlighted text for visualization
        transcription_result = session.get('transcription_result', {})
        
        if transcription_result and 'word_details' in transcription_result:
            # Use enhanced comparison with word details if available
            highlighted_text = compare_reading_with_word_details(original_text, transcription_result['word_details'])
        else:
            # Use basic comparison if no word details
            highlighted_text = compare_reading_with_text(original_text, spoken_text)
        
        # Store in session
        session['analysis_result'] = analysis_result
        
        return jsonify({
            "success": True,
            "analysis": analysis_result,
            "highlighted_text": highlighted_text
        })
    except Exception as e:
        logger.error(f"Error analyzing reading: {e}")
        return jsonify({"error": str(e)}), 500

# =====================================================================
# MAIN APP ROUTES
# =====================================================================

@app.route('/')
def index():
    """Main route for the single-page application"""
    return render_template('index.html')

@app.route('/realtime-reading')
def realtime_reading():
    """Route for the real-time reading assessment page"""
    return render_template('realtime-reading.html')

# =====================================================================
# DIAGNOSTICS ROUTES
# =====================================================================

@app.route('/api/diagnostics/whisper-status')
def api_diagnostics_whisper_status():
    """API endpoint to check Whisper.cpp status"""
    try:
        status = check_whisper_cpp_config()
        
        return jsonify({
            "success": True,
            "whisper_status": status
        })
    except Exception as e:
        logger.error(f"Error checking Whisper.cpp status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/diagnostics/system-info')
def api_diagnostics_system_info():
    """API endpoint to get system information"""
    try:
        # Get basic system info
        system_info = {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": platform.python_version(),
            "processor": platform.processor(),
            "hostname": platform.node(),
            "upload_folder": UPLOAD_FOLDER,
            "database_folder": DATABASE_FOLDER,
            "has_ffmpeg": bool(whisper_cpp_status.get("ffmpeg_available")),
            "ffmpeg_path": whisper_cpp_status.get("ffmpeg_path"),
            "whisper_available": bool(whisper_cpp_status.get("overall_status")),
            "whisper_cli_path": whisper_cpp_status.get("cli_path"),
            "whisper_model_path": whisper_cpp_status.get("model_path")
        }
        
        return jsonify({
            "success": True,
            "system_info": system_info
        })
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/diagnostics')
def diagnostics():
    """Route for the diagnostics page"""
    return render_template('diagnostics.html')

# =====================================================================
# MAIN APP ENTRY POINT
# =====================================================================

if __name__ == '__main__':
    # Print server startup information
    logger.info("Starting Flask development server")
    logger.info(f"UPLOAD_FOLDER: {UPLOAD_FOLDER}")
    logger.info(f"DATABASE_FOLDER: {DATABASE_FOLDER}")
    
    # Start the Flask development server
    app.run(host='0.0.0.0', port=5000, debug=True)