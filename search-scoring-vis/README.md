# Qdrant Score Decay Visualizer

A Gradio-based web application that visualizes and compares Qdrant's three score decay methods for time-based search result boosting.

Note: This visualisation tool was generated with Claude 4 Sonnet.

## What it does

This tool demonstrates how Qdrant's decay functions affect search scoring based on document creation time:
- **Linear Decay**: Steady decrease over time
- **Exponential Decay**: Rapid initial decrease, then gradual
- **Gaussian Decay**: Bell curve centered at target time

The app provides both mathematical visualizations and real query result comparisons using a local Qdrant instance.

## Setup

1. Install dependencies:
   ```bash
   poetry install
   ```

2. Ensure Qdrant is running locally on `localhost:6333`

## Usage

1. Run the visualization:
   ```bash
   poetry run python qdrant_vis.py
   ```

2. Open your browser to `http://localhost:7860`

3. Adjust parameters (scale value, time unit, midpoint) and click "Compare All Decay Methods"

The app will create sample data if your collection doesn't exist, then show both mathematical curves and actual query results for all three decay methods.
