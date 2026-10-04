# 🎮 Gesture Tic-Tac-Toe

A simple **Tic-Tac-Toe game controlled by hand gestures** using a laptop or desktop webcam.

Instead of using a mouse or keyboard, the player can use their **hand and finger movements** to interact with the game.

## 📌 Project Overview

**Gesture Tic-Tac-Toe** is a computer vision game that combines hand tracking with a traditional Tic-Tac-Toe game.

The project uses:

* **OpenCV** — captures and processes the webcam video.
* **MediaPipe** — detects and tracks the player's hand and finger landmarks.
* **Pygame** — creates the game window and displays the Tic-Tac-Toe board.
* **Python** — connects everything together and controls the game logic.

## 🛠️ Technologies Used

| Technology | Purpose                     |
| ---------- | --------------------------- |
| Python     | Main programming language   |
| OpenCV     | Webcam and image processing |
| MediaPipe  | Hand and finger tracking    |
| Pygame     | Game interface and graphics |

## 🧠 How It Works

The project works in several steps:

```text
Webcam
   ↓
OpenCV
   ↓
Capture Video
   ↓
MediaPipe
   ↓
Detect Hand & Finger
   ↓
Detect Gesture
   ↓
Python Game Logic
   ↓
Pygame
   ↓
Tic-Tac-Toe Board
```

### 1. OpenCV

OpenCV opens the computer's webcam and captures video frames.

It allows the program to see what is happening in front of the camera.

### 2. MediaPipe

MediaPipe detects the player's hand.

It provides **21 hand landmarks**, which can be used to track the position of the fingers.

For example:

```text
        ☝️
        |
        |
        ●
       / \
      /   \
     ●     ●
```

The program can use the position of the index finger to determine where the player is pointing.

### 3. Gesture Detection

The Python program checks the hand landmarks and determines what the player is doing.

For example:

```text
Pointing at a square
        ↓
Detect index finger
        ↓
Find finger position
        ↓
Find Tic-Tac-Toe square
        ↓
Select square
```

### 4. Pygame

Pygame creates the game window and draws:

* Tic-Tac-Toe board
* X and O
* Game messages
* Player information
* Buttons or other game elements

## 🎯 Game Concept

The Tic-Tac-Toe board contains 9 squares:

```text
┌─────┬─────┬─────┐
│  1  │  2  │  3  │
├─────┼─────┼─────┤
│  4  │  5  │  6  │
├─────┼─────┼─────┤
│  7  │  8  │  9  │
└─────┴─────┴─────┘
```

The player uses their finger to select a square.

For example:

```text
☝️
 ↓
Square 5
 ↓
X
```

The game then places the player's mark in that square.

## 💻 Requirements

Before running the project, make sure you have:

* Windows, macOS, or Linux
* Python 3.x
* A working webcam
* Internet connection for installing Python packages

## 📦 Installation

### 1. Clone the project

```bash
git clone <your-repository-url>
```

Go into the project folder:

```bash
cd gesture-tic-tac-toe
```

### 2. Install the required libraries

Run:

```bash
pip install opencv-python mediapipe pygame
```

### 3. Check the installation

You can test the libraries with:

```bash
python -c "import cv2, mediapipe, pygame; print('All libraries installed successfully!')"
```

If you see:

```text
All libraries installed successfully!
```

the installation is ready.

## ▶️ How to Run

Run the main Python file:

```bash
python main.py
```

Make sure your webcam is connected and available.

The game window should open and the camera should detect your hand.

## 🎮 How to Play

1. Start the game.
2. Allow access to your webcam if requested.
3. Place your hand in front of the camera.
4. Point at a Tic-Tac-Toe square.
5. Use the required gesture to select the square.
6. The game places your X or O.
7. Continue playing until one player wins or the game ends in a draw.

## 📁 Example Project Structure

```text
gesture-tic-tac-toe/
│
├── main.py
├── README.md
├── requirements.txt
│
├── assets/
│   ├── images/
│   └── sounds/
│
└── src/
    ├── hand_tracking.py
    ├── gesture_detection.py
    └── game.py
```

The exact structure may change depending on how the project is developed.

## 📋 requirements.txt

The project can use a `requirements.txt` file:

```text
opencv-python
mediapipe
pygame
```

Install all dependencies with:

```bash
pip install -r requirements.txt
```

## 🔧 Main Features

* 📷 Webcam control
* ✋ Hand tracking
* ☝️ Finger tracking
* 🖐️ Gesture detection
* 🎮 Interactive Tic-Tac-Toe
* 🖥️ Desktop/laptop support
* 🧠 Computer vision
* 🔄 Real-time interaction

## 🚧 Future Improvements

Possible improvements include:

* Add a computer opponent
* Add difficulty levels
* Add sound effects
* Add a score system
* Add a restart button
* Add more gestures
* Improve hand detection
* Add a start menu
* Add a game-over screen
* Support two players using gestures

## 🧩 Why These Technologies?

### OpenCV

OpenCV is useful because the project needs access to the webcam and real-time video processing.

### MediaPipe

MediaPipe is useful because it can detect and track the player's hand and finger positions.

### Pygame

Pygame is useful because it provides the tools needed to create the game window, graphics, and interaction.

Together, these technologies make it possible to create a game that can be controlled using hand gestures.

## 📚 Learning Goals

Through this project, we can learn about:

* Python programming
* Computer vision
* Webcam processing
* Hand tracking
* Gesture recognition
* Game development
* Event handling
* Basic game logic
* Using Python libraries together

## 👨‍💻 Project

**Project Name:** Gesture Tic-Tac-Toe

**Main Technologies:** Python, OpenCV, MediaPipe, Pygame

**Platform:** Desktop / Laptop

**Input:** Webcam + Hand Gestures

**Game:** Tic-Tac-Toe

---

## 📄 License

This project is created for **educational and learning purposes**.

