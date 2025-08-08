import gradio as gr
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from datetime import datetime, timedelta
from qdrant_client import QdrantClient, models
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Prefetch, FormulaQuery,
    SumExpression, GaussDecayExpression, LinDecayExpression,
    ExpDecayExpression, DecayParamsExpression, DatetimeExpression,
    DatetimeKeyExpression
)
import pandas as pd
import io
import warnings
warnings.filterwarnings("ignore")

# Initialize Qdrant client (you may need to adjust the connection parameters)
def get_qdrant_client():
    try:
        # Default local Qdrant instance
        client = QdrantClient("localhost", port=6333)
        return client
    except Exception as e:
        print(f"Error connecting to Qdrant: {e}")
        return None

def create_sample_collection_if_needed(client, collection_name):
    """Create a sample collection with datetime data if it doesn't exist"""
    try:
        collections = client.get_collections().collections
        collection_names = [col.name for col in collections]

        if collection_name not in collection_names:
            # Create collection
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=128, distance=Distance.COSINE),
            )

            # Add sample points with datetime payload
            current_time = datetime.now()
            sample_points = []

            for i in range(100):
                # Create points with varying timestamps (last 30 days)
                time_offset = timedelta(days=np.random.uniform(0, 30))
                created_time = current_time - time_offset

                sample_points.append(
                    PointStruct(
                        id=i,
                        vector=np.random.random(128).tolist(),
                        payload={
                            "created_time": created_time.isoformat(),
                            "title": f"Document {i}",
                            "category": np.random.choice(["tech", "business", "science"])
                        }
                    )
                )

            client.upsert(collection_name=collection_name, points=sample_points)
            print(f"Created sample collection '{collection_name}' with {len(sample_points)} points")

        return True

    except Exception as e:
        print(f"Error creating collection: {e}")
        return False

def query_with_decay(client, collection_name, decay_type, scale_value=7, scale_unit="days", midpoint=0.5):
    """Query Qdrant with different decay functions applied to created_time"""
    try:
        # Convert scale to seconds based on unit
        scale_multipliers = {
            "hours": 3600,
            "days": 24 * 3600,
            "weeks": 7 * 24 * 3600,
            "months": 30 * 24 * 3600,  # Approximate
            "years": 365 * 24 * 3600,  # Approximate
            "decades": 10 * 365 * 24 * 3600  # Approximate
        }

        scale_seconds = scale_value * scale_multipliers[scale_unit]

        # Current time for the target
        current_time = datetime.now()

        # Create the appropriate decay expression
        if decay_type == "linear":
            decay_expr = LinDecayExpression(
                lin_decay=DecayParamsExpression(
                    x=DatetimeKeyExpression(datetime_key="created_time"),
                    target=DatetimeExpression(datetime=current_time.isoformat()),
                    scale=scale_seconds,
                    midpoint=midpoint
                )
            )
        elif decay_type == "exponential":
            decay_expr = ExpDecayExpression(
                exp_decay=DecayParamsExpression(
                    x=DatetimeKeyExpression(datetime_key="created_time"),
                    target=DatetimeExpression(datetime=current_time.isoformat()),
                    scale=scale_seconds,
                    midpoint=midpoint
                )
            )
        elif decay_type == "gaussian":
            decay_expr = GaussDecayExpression(
                gauss_decay=DecayParamsExpression(
                    x=DatetimeKeyExpression(datetime_key="created_time"),
                    target=DatetimeExpression(datetime=current_time.isoformat()),
                    scale=scale_seconds,
                    midpoint=midpoint
                )
            )
        else:
            raise ValueError(f"Unknown decay type: {decay_type}")

        # Query with prefetch and formula
        results = client.query_points(
            collection_name=collection_name,
            prefetch=Prefetch(
                query=np.random.random(384).tolist(),  # Random query vector
                limit=50
            ),
            query=FormulaQuery(
                formula=SumExpression(
                    sum=[
                        "$score",  # Original similarity score
                        decay_expr  # Time-based decay boost
                    ]
                )
            ),
            limit=30,
            with_payload=True
        )

        return results

    except Exception as e:
        print(f"Error querying with decay: {e}")
        return None

def plot_decay_functions(scale_value=7, scale_unit="days", midpoint=0.5):
    """Plot the mathematical decay functions for visualization"""
    # Time range in the selected unit from current time
    x_units = np.linspace(-scale_value*2, scale_value*2, 1000)

    # Convert to seconds for calculation
    scale_multipliers = {
        "hours": 3600,
        "days": 24 * 3600,
        "weeks": 7 * 24 * 3600,
        "months": 30 * 24 * 3600,
        "years": 365 * 24 * 3600,
        "decades": 10 * 365 * 24 * 3600
    }

    x_seconds = x_units * scale_multipliers[scale_unit]
    scale_seconds = scale_value * scale_multipliers[scale_unit]

    # Calculate decay functions
    def linear_decay(x, scale, midpoint):
        return np.maximum(0, -(1-midpoint)/scale * np.abs(x) + 1)

    def exponential_decay(x, scale, midpoint):
        return np.exp(np.log(midpoint)/scale * np.abs(x))

    def gaussian_decay(x, scale, midpoint):
        return np.exp(np.log(midpoint)/(scale**2) * x**2)

    y_linear = linear_decay(x_seconds, scale_seconds, midpoint)
    y_exp = exponential_decay(x_seconds, scale_seconds, midpoint)
    y_gauss = gaussian_decay(x_seconds, scale_seconds, midpoint)

    # Create plot
    fig, ax = plt.subplots(figsize=(12, 8))

    ax.plot(x_units, y_linear, 'g-', linewidth=2, label='Linear Decay', alpha=0.8)
    ax.plot(x_units, y_exp, 'r-', linewidth=2, label='Exponential Decay', alpha=0.8)
    ax.plot(x_units, y_gauss, 'purple', linewidth=2, label='Gaussian Decay', alpha=0.8)

    # Add vertical line at current time (x=0)
    ax.axvline(x=0, color='black', linestyle='--', alpha=0.7, label='Current Time')

    # Add horizontal line at midpoint
    ax.axhline(y=midpoint, color='orange', linestyle=':', alpha=0.7,
               label=f'Midpoint ({midpoint})')

    # Formatting
    ax.set_xlabel(f'{scale_unit.title()} from Current Time (Scale: {scale_value} {scale_unit})', fontsize=12)
    ax.set_ylabel('Decay Score Boost (0-1)', fontsize=12)
    ax.set_title('Qdrant Decay Functions: Score Boosting Over Time', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=11)
    ax.set_ylim(0, 1.1)

    # Add annotations
    ax.annotate(f'Older documents\n(lower boost)',
                xy=(-scale_value, 0.2), xytext=(-scale_value*1.5, 0.4),
                arrowprops=dict(arrowstyle='->', alpha=0.6),
                fontsize=10, ha='center')

    ax.annotate(f'Recent documents\n(higher boost)',
                xy=(0, 1), xytext=(scale_value*0.5, 0.8),
                arrowprops=dict(arrowstyle='->', alpha=0.6),
                fontsize=10, ha='center')

    plt.tight_layout()
    return fig

def visualize_query_results_comparison(client, collection_name, scale_value, scale_unit, midpoint):
    """Visualize query results from all three decay methods side by side"""
    decay_types = ["linear", "exponential", "gaussian"]
    all_results = {}
    colors = ['green', 'red', 'purple']

    # Query with each decay type
    for decay_type in decay_types:
        results = query_with_decay(client, collection_name, decay_type, scale_value, scale_unit, midpoint)
        if results and results.points:
            all_results[decay_type] = results

    if not all_results:
        return None, "No results found or connection error"

    # Create comparison plots
    fig = plt.figure(figsize=(18, 12))

    # Main comparison plot (top)
    ax_main = plt.subplot(2, 2, (1, 2))

    # Plot results for each decay type
    for i, (decay_type, results) in enumerate(all_results.items()):
        scores = []
        time_diffs = []
        current_time = datetime.now()

        for point in results.points:
            scores.append(point.score)
            created_time = datetime.fromisoformat(point.payload['created_time'].replace('Z', '+00:00').replace('+00:00', ''))

            # Convert time difference to the selected unit
            time_diff_seconds = (current_time - created_time).total_seconds()

            scale_multipliers = {
                "hours": 3600,
                "days": 24 * 3600,
                "weeks": 7 * 24 * 3600,
                "months": 30 * 24 * 3600,
                "years": 365 * 24 * 3600,
                "decades": 10 * 365 * 24 * 3600
            }

            time_diff_units = time_diff_seconds / scale_multipliers[scale_unit]
            time_diffs.append(-time_diff_units)  # Negative because past dates

        # Scatter plot for this decay type
        scatter = ax_main.scatter(time_diffs, scores, alpha=0.7, s=50,
                                c=colors[i], label=f'{decay_type.title()} Decay')

    ax_main.set_xlabel(f'{scale_unit.title()} from Current Time', fontsize=12)
    ax_main.set_ylabel('Final Score (Similarity + Decay Boost)', fontsize=12)
    ax_main.set_title('Query Results Comparison: All Decay Methods', fontsize=14, fontweight='bold')
    ax_main.grid(True, alpha=0.3)
    ax_main.axvline(x=0, color='black', linestyle='--', alpha=0.7, label='Current Time')
    ax_main.legend(fontsize=11)

    # Individual score distributions (bottom row)
    for i, (decay_type, results) in enumerate(all_results.items()):
        ax = plt.subplot(2, 3, 4 + i)

        scores = [point.score for point in results.points]
        ax.hist(scores, bins=12, alpha=0.7, color=colors[i], edgecolor='black')
        ax.set_xlabel('Final Score')
        ax.set_ylabel('Count')
        ax.set_title(f'{decay_type.title()} Score Distribution')
        ax.grid(True, alpha=0.3)

        # Add statistics
        mean_score = np.mean(scores)
        ax.axvline(mean_score, color='darkred', linestyle=':', linewidth=2,
                  label=f'Mean: {mean_score:.3f}')
        ax.legend()

    plt.tight_layout()

    # Create comprehensive results table
    comparison_data = []
    for decay_type, results in all_results.items():
        current_time = datetime.now()
        for point in results.points[:10]:  # Top 10 for each method
            created_time = datetime.fromisoformat(point.payload['created_time'].replace('Z', '+00:00').replace('+00:00', ''))

            # Convert time difference to the selected unit
            time_diff_seconds = (current_time - created_time).total_seconds()
            scale_multipliers = {
                "hours": 3600,
                "days": 24 * 3600,
                "weeks": 7 * 24 * 3600,
                "months": 30 * 24 * 3600,
                "years": 365 * 24 * 3600,
                "decades": 10 * 365 * 24 * 3600
            }
            time_diff_units = time_diff_seconds / scale_multipliers[scale_unit]

            comparison_data.append({
                'Decay Method': decay_type.title(),
                'Title': point.payload['title'],
                f'{scale_unit.title()} Ago': f"{time_diff_units:.1f}",
                'Final Score': f"{point.score:.4f}",
                'Rank': len([p for p in results.points if p.score > point.score]) + 1
            })

    results_df = pd.DataFrame(comparison_data)

    return fig, results_df.to_string(index=False)

def main_visualization(collection_id, scale_value, scale_unit, midpoint):
    """Main function that creates the complete visualization"""
    client = get_qdrant_client()

    if not client:
        return None, None, "❌ Could not connect to Qdrant. Please ensure Qdrant is running on localhost:6333"

    # Validate collection exists or create sample
    if not create_sample_collection_if_needed(client, collection_id):
        return None, None, f"❌ Could not access or create collection '{collection_id}'"

    try:
        # Generate mathematical visualization with proper parameter passing
        math_plot = plot_decay_functions(scale_value=scale_value, scale_unit=scale_unit, midpoint=midpoint)

        # Generate comparison visualization for all decay methods with proper parameter passing
        results_plot, results_table = visualize_query_results_comparison(
            client, collection_id, scale_value=scale_value, scale_unit=scale_unit, midpoint=midpoint
        )

        if results_plot is None:
            return math_plot, None, f"✅ Mathematical visualization complete. Query results: {results_table}"

        return math_plot, results_plot, f"✅ Analysis complete for collection '{collection_id}' comparing all decay methods (Scale: {scale_value} {scale_unit})"

    except Exception as e:
        return None, None, f"❌ Error: {str(e)}"

# Create Gradio interface
with gr.Blocks(title="Qdrant Score Decay Visualizer", theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
    # 🚀 Qdrant Score Decay Methods Visualizer

    This application demonstrates **all three score decay methods** in Qdrant for time-based score boosting.
    The decay functions modify search results based on document creation time, giving fresher content higher scores.

    **Compare All Decay Functions:**
    - **Linear**: Steady decrease over time (green)
    - **Exponential**: Rapid initial decrease, then gradual (red)
    - **Gaussian**: Bell curve centered at target time (purple)

    > **Note**: This app connects to a local Qdrant instance at `localhost:6333`. If the collection doesn't exist, sample data will be created.
    """)

    with gr.Row():
        with gr.Column(scale=1):
            collection_input = gr.Textbox(
                label="Collection ID",
                value="sample_documents",
                placeholder="Enter collection name",
                info="Name of the Qdrant collection to query"
            )

            decay_type = gr.Radio(
                choices=["linear", "exponential", "gaussian"],
                value="gaussian",
                label="Decay Function Type (for Mathematical Plot)",
                info="Shows mathematical curves - comparison uses all three",
                visible=False  # Hide since we're comparing all methods
            )

            scale_value = gr.Slider(
                minimum=1, maximum=50, value=7, step=1,
                label="Scale Value",
                info="Time period over which decay occurs"
            )

            scale_unit = gr.Dropdown(
                choices=["hours", "days", "weeks", "months", "years", "decades"],
                value="days",
                label="Scale Unit",
                info="Time unit for the decay scale"
            )

            midpoint = gr.Slider(
                minimum=0.1, maximum=0.9, value=0.5, step=0.1,
                label="Midpoint",
                info="Decay value when x equals scale"
            )

            analyze_btn = gr.Button("🔍 Compare All Decay Methods", variant="primary", size="lg")

    status_output = gr.Textbox(label="Status", interactive=False)

    with gr.Row():
        math_plot = gr.Plot(label="Mathematical Decay Functions (All Methods)", scale=1)
        results_plot = gr.Plot(label="Query Results Comparison (All Methods)", scale=1)

    # Event handlers
    analyze_btn.click(
        fn=main_visualization,
        inputs=[collection_input, scale_value, scale_unit, midpoint],
        outputs=[math_plot, results_plot, status_output]
    )

    # Auto-update when parameters change
    for component in [scale_value, scale_unit, midpoint]:
        component.change(
            fn=main_visualization,
            inputs=[collection_input, scale_value, scale_unit, midpoint],
            outputs=[math_plot, results_plot, status_output]
        )

    gr.Markdown("""
    ---

    ## 📊 Understanding the Visualizations

    **Left Plot - Mathematical Functions:**
    - Shows how all three decay functions behave over time
    - X-axis: Days from current time (negative = past, 0 = now)
    - Y-axis: Decay boost score (0-1)
    - Colors: Green (Linear), Red (Exponential), Purple (Gaussian)

    **Right Plot - Query Results Comparison:**
    - Top: Scatter plot comparing all three methods on the same dataset
    - Bottom: Score distributions for each decay method
    - Same color coding as mathematical functions

    ## ⚙️ Parameters
    - **Scale Value**: Numeric value for the decay period
    - **Scale Unit**: Time unit (hours, days, weeks, months, years, decades)
    - **Midpoint**: Score value at the scale distance (affects all methods)
    - **Collection**: Your Qdrant collection (sample data created if needed)

    ## 🕒 Time Scale Examples
    - **Hours**: For real-time applications (news, social media)
    - **Days**: For content freshness (blogs, articles)
    - **Weeks**: For periodic content (reports, updates)
    - **Months**: For seasonal relevance
    - **Years**: For long-term trends
    - **Decades**: For historical analysis

    ## 🔧 Technical Notes
    - Uses Qdrant's Formula Query API with datetime expressions
    - Compares all three decay methods simultaneously
    - Shows ranking differences between decay approaches
    - Requires a `created_time` field in document payload
    """)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
