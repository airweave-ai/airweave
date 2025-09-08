"""LLM-based evaluation of search results for testing.

This module provides utilities to use LLMs to evaluate the quality of search results
in an automated testing environment.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional
import openai

# Set up logging
logger = logging.getLogger(__name__)



class SearchResultEvaluator:
    """Evaluates search results using LLM-based techniques.

    This class provides methods to evaluate the quality of search results
    using either:
    1. An LLM API (if available)
    2. Simple keyword matching as a fallback
    """

    def __init__(self, llm_api_key: Optional[str] = None):
        """Initialize the evaluator.

        Args:
            llm_api_key: API key for the LLM service (optional)
        """
        self.llm_api_key = llm_api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")

    def evaluate(
        self,
        query: str,
        results: List[Dict[str, Any]],
        expected_content_keywords: Optional[List[str]] = None,
        minimum_score: float = 0.7,
        minimum_relevant_results: int = 3,
    ) -> Dict[str, Any]:
        """Evaluate search results quality.

        Args:
            query: The search query
            results: List of search results
            expected_content_keywords: Keywords that should appear in good results
            minimum_score: Minimum acceptable quality score (0-1)
            minimum_relevant_results: Minimum number of relevant results expected

        Returns:
            Dict with evaluation metrics
        """
        expected_keywords = expected_content_keywords or []

        # Use LLM if API key is available, otherwise fall back to simple evaluation
        if self.llm_api_key:
            evaluation = self._evaluate_with_llm(query, results, expected_keywords)
        else:
            logger.warning("No LLM API key provided, falling back to simple evaluation.")
            evaluation = self._simple_evaluation(query, results, expected_keywords)

        # Add pass/fail status
        evaluation["passed"] = (
            evaluation["score"] >= minimum_score
            and evaluation["relevant_results"] >= minimum_relevant_results
        )

        return evaluation

    def _evaluate_with_llm(
        self, query: str, results: List[Dict[str, Any]], expected_content_keywords: List[str]
    ) -> Dict[str, Any]:
        """Use OpenAI's API to evaluate search results.

        Args:
            query: The search query
            results: List of search results
            expected_content_keywords: Keywords that should appear in good results

        Returns:
            Dict with evaluation metrics
        """
        try:
            # Check if OpenAI module is available
            if 'openai' not in globals():
                logger.error("OpenAI package not installed, falling back to simple evaluation")
                return self._simple_evaluation(query, results, expected_content_keywords)

            # Set up OpenAI client
            client = openai.OpenAI(api_key=self.llm_api_key)

            # Format results for better readability in the prompt
            formatted_results = json.dumps(results, indent=2)
            keywords_str = ", ".join(expected_content_keywords) if expected_content_keywords else "None specified"

            # Create the evaluation prompt
            prompt = f"""
            Evaluate the quality of these search results for the query: "{query}".

            Search Results:
            {formatted_results}

            Expected keywords that should appear in good results: {keywords_str}

            Please evaluate the results on the following metrics:
            1. Relevance (0-1): How relevant are the results to the query?
            2. Completeness (0-1): How well do the results cover the expected keywords and topics?
            3. Diversity (0-1): How diverse are the results in covering different aspects?
            4. Relevant Results Count: How many results are actually relevant to the query?

            Please provide your evaluation in JSON format with these fields:
            - relevance: float (0-1)
            - completeness: float (0-1)
            - diversity: float (0-1)
            - relevant_results: int
            - score: float (0-1, weighted average of other metrics)
            - feedback: string (brief explanation of the evaluation)
            """

            # Call the OpenAI API
            response = client.chat.completions.create(
                model="gpt-5-nano",  # Use an appropriate model
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )

            # Parse the response
            evaluation = json.loads(response.choices[0].message.content)

            # Ensure all required fields are present
            required_fields = ["relevance", "completeness", "diversity", "relevant_results", "score", "feedback"]
            for field in required_fields:
                if field not in evaluation:
                    logger.warning(f"Field {field} missing from LLM evaluation, adding default value")
                    if field == "relevant_results":
                        evaluation[field] = 0
                    elif field == "feedback":
                        evaluation[field] = "No feedback provided by LLM"
                    else:
                        evaluation[field] = 0.0  # Default value for missing metrics

            return evaluation

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            # Fall back to simple evaluation
            return self._simple_evaluation(query, results, expected_content_keywords)

    def _simple_evaluation(
        self, query: str, results: List[Dict[str, Any]], expected_content_keywords: List[str]
    ) -> Dict[str, Any]:
        """Simple keyword-based evaluation as fallback.

        Args:
            query: The search query
            results: List of search results
            expected_content_keywords: Keywords that should appear in good results

        Returns:
            Dict with evaluation metrics
        """
        # No results - return poor score
        if not results:
            return {
                "relevance": 0.0,
                "completeness": 0.0,
                "diversity": 0.0,
                "relevant_results": 0,
                "score": 0.0,
                "feedback": "No results provided",
            }

        # If no keywords provided, check if query terms appear in results
        if not expected_content_keywords:
            expected_content_keywords = [term.lower() for term in query.split() if len(term) > 3]

        relevant_count = 0
        keyword_matches = 0

        for result in results:
            # Convert result to string for simple text matching
            content = json.dumps(result).lower()
            query_terms_present = any(
                term.lower() in content for term in query.split() if len(term) > 3
            )
            keywords_present = any(
                keyword.lower() in content for keyword in expected_content_keywords
            )

            # Count as relevant if either query terms or expected keywords are present
            if query_terms_present or keywords_present:
                relevant_count += 1

            # Count total keyword matches
            keyword_matches += sum(
                1 for keyword in expected_content_keywords if keyword.lower() in content
            )

        # Calculate metrics
        total_possible_matches = len(expected_content_keywords) * len(results)
        completeness = keyword_matches / total_possible_matches if total_possible_matches > 0 else 0
        relevance = relevant_count / len(results) if results else 0

        # Fixed diversity estimate (can't easily determine with simple matching)
        diversity = 0.5

        # Calculate weighted score
        score = relevance * 0.5 + completeness * 0.3 + diversity * 0.2

        # Generate feedback
        if relevant_count == 0:
            feedback = "No relevant results found containing query terms or expected keywords."
        elif relevance < 0.5:
            feedback = (
                f"Low relevance ({relevance:.2f}): "
                f"Less than half of results contain relevant content."
            )
        elif completeness < 0.3:
            feedback = (
                f"Low completeness ({completeness:.2f}): Expected keywords not well represented."
            )
        else:
            feedback = f"Found {relevant_count} relevant results out of {len(results)}."

        return {
            "relevance": relevance,
            "completeness": completeness,
            "diversity": diversity,
            "relevant_results": relevant_count,
            "score": score,
            "feedback": feedback,
        }


# Convenience function for easily evaluating results
def evaluate_search_results(
    query: str,
    results: List[Dict[str, Any]],
    expected_content_keywords: Optional[List[str]] = None,
    minimum_score: float = 0.7,
    minimum_relevant_results: int = 3,
) -> Dict[str, Any]:
    """Convenience function to evaluate search results.

    Args:
        query: The search query
        results: List of search results
        expected_content_keywords: Keywords that should appear in good results
        minimum_score: Minimum acceptable quality score (0-1)
        minimum_relevant_results: Minimum number of relevant results expected

    Returns:
        Dict with evaluation metrics
    """
    evaluator = SearchResultEvaluator()
    return evaluator.evaluate(
        query=query,
        results=results,
        expected_content_keywords=expected_content_keywords,
        minimum_score=minimum_score,
        minimum_relevant_results=minimum_relevant_results,
    )
