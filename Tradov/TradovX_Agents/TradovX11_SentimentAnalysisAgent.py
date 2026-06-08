#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovX_Agents
Module: TradovX11_SentimentAnalysisAgent.py
Purpose: TRADOV - Automated TRAD Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    TRADOV - Automated TRAD Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
from datetime import datetime, timedelta, UTC
from typing import Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
import re
from concurrent.futures import ThreadPoolExecutor
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np

warnings.filterwarnings("ignore")

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
# NLP Libraries
from transformers import (  # noqa: E402
    AutoTokenizer,
    AutoModelForSequenceClassification,
    pipeline,
)
import torch  # noqa: E402
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    spacy = None  # type: ignore
    SPACY_AVAILABLE = False
from textblob import TextBlob  # noqa: E402
import nltk  # noqa: E402
from nltk.tokenize import sent_tokenize, word_tokenize  # noqa: E402
from nltk.corpus import stopwords  # noqa: E402

# Audio Processing
try:
    import whisper

    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

# Web Scraping
# Web Scraping (optional — requires credentials)
try:
    import praw  # Reddit API
    PRAW_AVAILABLE = True
except ImportError:
    praw = None  # type: ignore
    PRAW_AVAILABLE = False
try:
    import tweepy  # Twitter API
    TWEEPY_AVAILABLE = True
except ImportError:
    tweepy = None  # type: ignore
    TWEEPY_AVAILABLE = False

# Language Detection and Translation (optional)
try:
    from langdetect import detect
    LANGDETECT_AVAILABLE = True
except ImportError:
    detect = None  # type: ignore
    LANGDETECT_AVAILABLE = False
try:
    from googletrans import Translator
    GOOGLETRANS_AVAILABLE = True
except ImportError:
    Translator = None  # type: ignore
    GOOGLETRANS_AVAILABLE = False

# Topic Modeling
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.decomposition import LatentDirichletAllocation  # noqa: E402

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger  # noqa: E402
from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler  # noqa: E402
try:
    from Tradov.TradovU_Utilities.TradovU07_Constants import MAX_SENTIMENT_HISTORY
except ImportError:
    MAX_SENTIMENT_HISTORY = 1000
import logging  # noqa: E402

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Model configurations
FINBERT_MODEL = "yiyanghkust/finbert-tone"
ROBERTA_MODEL = "cardiffnlp/twitter-roberta-base-sentiment"
NER_MODEL = "dbmdz/bert-large-cased-finetuned-conll03-english"

# Sentiment thresholds
STRONG_POSITIVE_THRESHOLD = 0.7
POSITIVE_THRESHOLD = 0.3
NEGATIVE_THRESHOLD = -0.3
STRONG_NEGATIVE_THRESHOLD = -0.7

# Source weights
SOURCE_WEIGHTS = {
    "federal_reserve": 3.0,
    "earnings_calls": 2.5,
    "major_news": 2.0,
    "analyst_reports": 1.8,
    "social_media": 1.2,
    "reddit": 1.0,
    "twitter": 1.0,
}

# Entity categories
ENTITY_CATEGORIES = {
    "central_banks": ["Federal Reserve", "Fed", "FOMC", "ECB", "BOJ", "BOE"],
    "officials": ["Jerome Powell", "Janet Yellen", "Christine Lagarde"],
    "companies": ["Apple", "Microsoft", "Amazon", "Google", "Meta", "Tesla"],
    "sectors": ["Technology", "Financials", "Healthcare", "Energy", "Consumer"],
    "indicators": ["CPI", "GDP", "Unemployment", "Inflation", "Interest Rates"],
}


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class SentimentScore:
    """Individual sentiment measurement"""

    value: float  # -1 to 1
    confidence: float  # 0 to 1
    source: str
    text_snippet: str
    timestamp: datetime
    entities: list[str] = field(default_factory=list)
    language: str = "en"

    @property
    def weighted_score(self) -> float:
        """Get confidence-weighted sentiment score"""
        return self.value * self.confidence


@dataclass
class EntitySentiment:
    """Sentiment tracking for specific entity"""

    entity_name: str
    entity_type: str
    sentiment_scores: deque = field(default_factory=lambda: deque(maxlen=100))
    mention_count: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def current_sentiment(self) -> float:
        """Get current average sentiment"""
        if not self.sentiment_scores:
            return 0.0
        recent_scores = list(self.sentiment_scores)[-10:]
        return np.mean([s.weighted_score for s in recent_scores])

    @property
    def sentiment_momentum(self) -> float:
        """Calculate sentiment trend"""
        if len(self.sentiment_scores) < 2:
            return 0.0
        recent = list(self.sentiment_scores)[-5:]
        older = list(self.sentiment_scores)[-10:-5]
        if not older:
            return 0.0
        recent_avg = np.mean([s.weighted_score for s in recent])
        older_avg = np.mean([s.weighted_score for s in older])
        return recent_avg - older_avg


@dataclass
class MarketEvent:
    """Detected market-moving event"""

    event_type: str
    description: str
    impact_score: float  # 0 to 1
    sentiment: float
    entities: list[str]
    source: str
    timestamp: datetime
    predicted_duration: timedelta
    confidence: float


@dataclass
class SentimentReport:
    """Comprehensive sentiment analysis report"""

    overall_sentiment: float
    sentiment_distribution: dict[str, float]
    top_entities: list[tuple[str, float]]
    detected_events: list[MarketEvent]
    sentiment_momentum: float
    regime: str  # 'bullish', 'bearish', 'neutral', 'mixed'
    confidence: float
    key_themes: list[str]
    warnings: list[str]


# ==============================================================================
# ENHANCED SENTIMENT ANALYSIS AGENT
# ==============================================================================
class EnhancedSentimentAnalysisAgent:
    """
    Advanced sentiment analysis agent with institutional-grade NLP capabilities.

    Analyzes multiple data sources including earnings calls, Fed communications,
    news, and social media to provide comprehensive market sentiment insights.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize enhanced sentiment analysis agent"""
        self.logger = TradovLogger.get_logger(self.__class__.__name__)
        self.error_handler = TradovErrorHandler()

        # Configuration
        self.config = config or {}
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Models
        self.models = {}
        self.tokenizers = {}
        self.pipelines = {}

        # Data storage
        self.sentiment_history = deque(maxlen=MAX_SENTIMENT_HISTORY)
        self.entity_sentiments = defaultdict(lambda: EntitySentiment("", ""))
        self.recent_events = deque(maxlen=100)

        # Language support
        self.translator = Translator()
        self.supported_languages = ["en", "es", "fr", "de", "zh", "ja"]

        # Audio transcription
        self.whisper_model = None

        # API clients
        self.reddit_client = None
        self.twitter_client = None

        # Threading
        self.executor = ThreadPoolExecutor(max_workers=10)

        # Initialize components
        self._initialize_models()
        self._initialize_apis()
        self._download_nltk_data()

        self.logger.info("✅ Enhanced Sentiment Analysis Agent initialized")

    # ==========================================================================
    # INITIALIZATION
    # ==========================================================================

    def _initialize_models(self):
        """Initialize all NLP models"""
        try:
            # FinBERT for financial sentiment
            self.logger.info("Loading FinBERT model...")
            self.tokenizers["finbert"] = AutoTokenizer.from_pretrained(FINBERT_MODEL)
            self.models["finbert"] = AutoModelForSequenceClassification.from_pretrained(
                FINBERT_MODEL
            ).to(self.device)

            # RoBERTa for social media
            self.logger.info("Loading RoBERTa model...")
            self.pipelines["roberta"] = pipeline(
                "sentiment-analysis",
                model=ROBERTA_MODEL,
                device=0 if torch.cuda.is_available() else -1,
            )

            # NER for entity recognition
            self.logger.info("Loading NER model...")
            self.pipelines["ner"] = pipeline(
                "ner",
                model=NER_MODEL,
                aggregation_strategy="simple",
                device=0 if torch.cuda.is_available() else -1,
            )

            # Question answering for specific queries
            self.pipelines["qa"] = pipeline(
                "question-answering", device=0 if torch.cuda.is_available() else -1
            )

            # SpaCy for linguistic analysis
            if SPACY_AVAILABLE:
                self.nlp = spacy.load("en_core_web_lg")
            else:
                self.nlp = None

            # Whisper for audio transcription
            if WHISPER_AVAILABLE:
                self.logger.info("Loading Whisper model...")
                self.whisper_model = whisper.load_model("base")

            self.logger.info("All NLP models loaded successfully")

        except Exception as e:
            self.logger.error("Model initialization error: %s", e)
            self.error_handler.handle_error(e, {"method": "_initialize_models"})

    def _initialize_apis(self):
        """Initialize API clients for data sources"""
        try:
            # Reddit API
            if PRAW_AVAILABLE and all(key in self.config for key in ["reddit_client_id", "reddit_secret"]):  # noqa: E501
                self.reddit_client = praw.Reddit(
                    client_id=self.config["reddit_client_id"],
                    client_secret=self.config["reddit_secret"],
                    user_agent="TradovSentimentBot/1.0",
                )
                self.logger.info("Reddit API initialized")

            # Twitter API
            if TWEEPY_AVAILABLE and "twitter_bearer_token" in self.config:
                self.twitter_client = tweepy.Client(
                    bearer_token=self.config["twitter_bearer_token"]
                )
                self.logger.info("Twitter API initialized")

        except Exception as e:
            self.logger.warning("API initialization error: %s", e)

    def _download_nltk_data(self):
        """Download required NLTK data"""
        try:
            nltk.download("punkt", quiet=True)
            nltk.download("stopwords", quiet=True)
            nltk.download("vader_lexicon", quiet=True)
        except Exception as e:
            self.logger.warning("NLTK download error: %s", e)

    # ==========================================================================
    # EARNINGS CALL ANALYSIS
    # ==========================================================================

    async def analyze_earnings_call(
        self, transcript: str, company: str, quarter: str
    ) -> dict[str, Any]:
        """
        Analyze earnings call transcript for sentiment and key insights.

        Args:
            transcript: Full transcript text
            company: Company name
            quarter: Quarter identifier (e.g., "Q2 2025")

        Returns:
            Comprehensive analysis results
        """
        try:
            self.logger.info("Analyzing %s %s earnings call", company, quarter)

            # Split transcript into sections
            sections = self._split_earnings_sections(transcript)

            # Analyze each section
            section_sentiments = {}
            key_quotes = []
            entities_mentioned = set()

            for section_name, section_text in sections.items():
                # Get sentiment
                sentiment = await self._analyze_text_sentiment(
                    section_text, source=f"{company}_earnings"
                )
                section_sentiments[section_name] = sentiment

                # Extract key quotes
                quotes = self._extract_key_quotes(section_text, sentiment)
                key_quotes.extend(quotes)

                # Extract entities
                entities = await self._extract_entities(section_text)
                entities_mentioned.update(entities)

            # Analyze forward guidance
            guidance_sentiment = await self._analyze_guidance(
                sections.get("guidance", ""), sections.get("qa", "")
            )

            # Topic modeling
            topics = self._extract_topics(transcript)

            # Generate summary
            summary = {
                "company": company,
                "quarter": quarter,
                "overall_sentiment": np.mean(
                    [s.value for s in section_sentiments.values()]
                ),
                "section_sentiments": {
                    k: v.value for k, v in section_sentiments.items()
                },
                "guidance_sentiment": guidance_sentiment,
                "key_quotes": key_quotes[:5],
                "entities_mentioned": list(entities_mentioned),
                "main_topics": topics[:5],
                "confidence": np.mean(
                    [s.confidence for s in section_sentiments.values()]
                ),
            }

            # Update entity sentiments
            self._update_entity_sentiment(
                company, summary["overall_sentiment"], "earnings_call"
            )

            # Check for significant events
            event = self._check_earnings_event(summary)
            if event:
                self.recent_events.append(event)

            return summary

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "analyze_earnings_call", "company": company}
            )
            return {}

    def _split_earnings_sections(self, transcript: str) -> dict[str, str]:
        """Split earnings transcript into logical sections"""
        sections = {"prepared_remarks": "", "guidance": "", "qa": ""}

        # Common section markers
        qa_markers = ["question-and-answer", "q&a session", "now take questions"]
        guidance_markers = ["guidance", "outlook", "forecast", "expect"]

        lines = transcript.split("\n")
        current_section = "prepared_remarks"

        for line in lines:
            line_lower = line.lower()

            # Check for Q&A section
            if any(marker in line_lower for marker in qa_markers):
                current_section = "qa"

            # Check for guidance mentions
            elif current_section != "qa" and any(
                marker in line_lower for marker in guidance_markers
            ):
                if "guidance" not in sections:
                    sections["guidance"] = ""
                sections["guidance"] += line + "\n"

            sections[current_section] += line + "\n"

        return sections

    async def _analyze_guidance(self, guidance_text: str, qa_text: str) -> float:
        """Analyze forward guidance sentiment"""
        # Keywords indicating positive/negative guidance
        positive_guidance = [
            "raise guidance",
            "increase outlook",
            "better than expected",
            "strong momentum",
            "accelerating growth",
            "exceeding targets",
        ]

        negative_guidance = [
            "lower guidance",
            "reduce outlook",
            "challenging environment",
            "headwinds",
            "slower growth",
            "below expectations",
        ]

        combined_text = guidance_text + " " + qa_text
        combined_lower = combined_text.lower()

        # Count occurrences
        positive_count = sum(
            1 for phrase in positive_guidance if phrase in combined_lower
        )
        negative_count = sum(
            1 for phrase in negative_guidance if phrase in combined_lower
        )

        # Get ML sentiment
        ml_sentiment = await self._analyze_text_sentiment(combined_text, "guidance")

        # Combine rule-based and ML
        rule_sentiment = (positive_count - negative_count) / max(
            positive_count + negative_count, 1
        )

        return 0.7 * ml_sentiment.value + 0.3 * rule_sentiment

    def _extract_key_quotes(
        self, text: str, sentiment: SentimentScore
    ) -> list[dict[str, Any]]:
        """Extract impactful quotes from text"""
        sentences = sent_tokenize(text)
        quotes = []

        # Keywords that indicate important statements
        importance_keywords = [
            "expect",
            "believe",
            "forecast",
            "guidance",
            "outlook",
            "confident",
            "concern",
            "risk",
            "opportunity",
            "growth",
        ]

        for sentence in sentences:
            # Check if sentence contains important keywords
            if any(keyword in sentence.lower() for keyword in importance_keywords):
                # Get sentence sentiment
                sentence_sentiment = TextBlob(sentence).sentiment.polarity

                # If sentiment is strong or differs from overall, it's noteworthy
                if (
                    abs(sentence_sentiment) > 0.3
                    or abs(sentence_sentiment - sentiment.value) > 0.5
                ):
                    quotes.append(
                        {
                            "text": sentence.strip(),
                            "sentiment": sentence_sentiment,
                            "importance": abs(sentence_sentiment),
                        }
                    )

        # Sort by importance
        quotes.sort(key=lambda x: x["importance"], reverse=True)

        return quotes

    # ==========================================================================
    # FEDERAL RESERVE ANALYSIS
    # ==========================================================================

    async def analyze_fed_communication(
        self, text: str, comm_type: str, speaker: str | None = None
    ) -> dict[str, Any]:
        """
        Analyze Federal Reserve communications for policy signals.

        Args:
            text: Communication text
            comm_type: Type (FOMC_statement, speech, minutes, testimony)
            speaker: Speaker name if applicable

        Returns:
            Analysis with policy implications
        """
        try:
            self.logger.info("Analyzing Fed %s", comm_type)

            # Policy stance keywords
            hawkish_keywords = [
                "inflation concerns",
                "overheating",
                "raise rates",
                "tighten",
                "reduce accommodation",
                "upside risks",
                "above target",
            ]

            dovish_keywords = [
                "support growth",
                "maintain accommodation",
                "downside risks",
                "below target",
                "patience",
                "gradual",
                "data dependent",
            ]

            # Extract policy signals
            text_lower = text.lower()
            hawkish_score = sum(1 for kw in hawkish_keywords if kw in text_lower)
            dovish_score = sum(1 for kw in dovish_keywords if kw in text_lower)

            # ML sentiment analysis
            sentiment = await self._analyze_text_sentiment(text, "federal_reserve")

            # Analyze specific topics
            topics_analysis = {
                "inflation": self._analyze_topic_sentiment(text, "inflation"),
                "employment": self._analyze_topic_sentiment(text, "employment"),
                "growth": self._analyze_topic_sentiment(text, "growth"),
                "financial_conditions": self._analyze_topic_sentiment(
                    text, "financial conditions"
                ),
            }

            # Extract rate path implications
            rate_implications = self._extract_rate_implications(text)

            # Policy stance calculation
            policy_stance = (hawkish_score - dovish_score) / max(
                hawkish_score + dovish_score, 1
            )

            # Create analysis
            analysis = {
                "type": comm_type,
                "speaker": speaker,
                "overall_sentiment": sentiment.value,
                "policy_stance": policy_stance,  # -1 dovish to 1 hawkish
                "topics": topics_analysis,
                "rate_implications": rate_implications,
                "key_phrases": self._extract_policy_phrases(text),
                "confidence": sentiment.confidence,
                "timestamp": datetime.now(UTC),
            }

            # Create market event if significant
            if abs(policy_stance) > 0.5 or comm_type == "FOMC_statement":
                event = MarketEvent(
                    event_type="fed_communication",
                    description=f"{comm_type}: {'Hawkish' if policy_stance > 0 else 'Dovish'} tone",
                    impact_score=min(abs(policy_stance), 1.0),
                    sentiment=policy_stance,
                    entities=["Federal Reserve"] + ([speaker] if speaker else []),
                    source="federal_reserve",
                    timestamp=datetime.now(UTC),
                    predicted_duration=timedelta(days=2),
                    confidence=sentiment.confidence,
                )
                self.recent_events.append(event)

            return analysis

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "analyze_fed_communication", "type": comm_type}
            )
            return {}

    def _analyze_topic_sentiment(self, text: str, topic: str) -> dict[str, Any]:
        """Analyze sentiment for specific topic within text"""
        # Extract sentences mentioning topic
        sentences = sent_tokenize(text)
        topic_sentences = [s for s in sentences if topic.lower() in s.lower()]

        if not topic_sentences:
            return {"mentioned": False, "sentiment": 0.0, "prominence": 0.0}

        # Calculate sentiment
        sentiments = [TextBlob(s).sentiment.polarity for s in topic_sentences]

        return {
            "mentioned": True,
            "sentiment": np.mean(sentiments),
            "prominence": len(topic_sentences) / len(sentences),
            "key_statements": topic_sentences[:3],
        }

    def _extract_rate_implications(self, text: str) -> dict[str, Any]:
        """Extract interest rate implications from Fed text"""
        implications = {
            "direction": "neutral",
            "timing": "uncertain",
            "magnitude": "gradual",
        }

        text_lower = text.lower()

        # Direction signals
        if any(
            phrase in text_lower
            for phrase in ["raise rates", "increase rates", "tighten"]
        ):
            implications["direction"] = "increase"
        elif any(
            phrase in text_lower for phrase in ["cut rates", "lower rates", "ease"]
        ):
            implications["direction"] = "decrease"

        # Timing signals
        if any(phrase in text_lower for phrase in ["soon", "next meeting", "imminent"]):
            implications["timing"] = "near-term"
        elif any(
            phrase in text_lower for phrase in ["patient", "some time", "gradual"]
        ):
            implications["timing"] = "medium-term"

        # Magnitude signals
        if any(
            phrase in text_lower
            for phrase in ["aggressive", "substantial", "significant"]
        ):
            implications["magnitude"] = "large"
        elif any(phrase in text_lower for phrase in ["modest", "measured", "gradual"]):
            implications["magnitude"] = "small"

        return implications

    def _extract_policy_phrases(self, text: str) -> list[str]:
        """Extract key policy-related phrases"""
        # Key Fed phrases to look for
        key_patterns = [
            r"inflation.{0,20}(above|below|at|near).{0,20}target",
            r"labor market.{0,20}(strong|weak|tight|slack)",
            r"economic.{0,20}(growth|expansion|contraction)",
            r"financial.{0,20}conditions",
            r"policy.{0,20}(stance|path|normalization)",
        ]

        key_phrases = []
        for pattern in key_patterns:
            matches = re.findall(pattern, text.lower())
            key_phrases.extend(matches)

        return list(set(key_phrases))[:10]

    # ==========================================================================
    # MULTI-LANGUAGE SUPPORT
    # ==========================================================================

    async def analyze_multilingual_news(
        self, articles: list[dict[str, str]]
    ) -> dict[str, Any]:
        """
        Analyze news articles in multiple languages.

        Args:
            articles: List of articles with 'text', 'language', 'source' keys

        Returns:
            Aggregated sentiment analysis
        """
        results = []

        for article in articles:
            try:
                text = article["text"]
                lang = article.get("language", "en")

                # Detect language if not specified
                if lang == "auto":
                    lang = detect(text)

                # Translate if not English
                if lang != "en" and lang in self.supported_languages:
                    self.logger.info("Translating from %s to English", lang)
                    translated = self.translator.translate(text, src=lang, dest="en")
                    text = translated.text
                    translation_confidence = 0.8  # Reduced confidence for translations
                else:
                    translation_confidence = 1.0

                # Analyze sentiment
                sentiment = await self._analyze_text_sentiment(
                    text, source=article.get("source", "news")
                )

                # Adjust confidence for translation
                sentiment.confidence *= translation_confidence

                # Extract entities
                entities = await self._extract_entities(text)

                results.append(
                    {
                        "original_language": lang,
                        "sentiment": sentiment,
                        "entities": entities,
                        "source": article.get("source", "unknown"),
                        "headline": article.get("headline", "")[:100],
                    }
                )

            except Exception as e:
                self.logger.error("Error analyzing article: %s", e)
                continue

        # Aggregate results
        if results:
            aggregated = {
                "overall_sentiment": np.mean([r["sentiment"].value for r in results]),
                "confidence": np.mean([r["sentiment"].confidence for r in results]),
                "language_distribution": defaultdict(int),
                "entity_mentions": defaultdict(int),
                "source_sentiments": defaultdict(list),
            }

            for result in results:
                aggregated["language_distribution"][result["original_language"]] += 1
                aggregated["source_sentiments"][result["source"]].append(
                    result["sentiment"].value
                )

                for entity in result["entities"]:
                    aggregated["entity_mentions"][entity] += 1

            # Calculate source averages
            aggregated["source_sentiments"] = {
                source: np.mean(sentiments)
                for source, sentiments in aggregated["source_sentiments"].items()
            }

            return aggregated

        return {}

    # ==========================================================================
    # SOCIAL MEDIA ANALYSIS
    # ==========================================================================

    async def analyze_social_media(
        self, platforms: list[str] = None
    ) -> dict[str, Any]:
        """Analyze sentiment across social media platforms"""
        if platforms is None:
            platforms = ["reddit", "twitter"]
        results = {}

        if "reddit" in platforms and self.reddit_client:
            results["reddit"] = await self._analyze_reddit()

        if "twitter" in platforms and self.twitter_client:
            results["twitter"] = await self._analyze_twitter()

        # Aggregate across platforms
        if results:
            overall_sentiment = np.mean(
                [r["sentiment"] for r in results.values() if "sentiment" in r]
            )

            return {
                "overall_sentiment": overall_sentiment,
                "platform_sentiments": results,
                "trending_topics": self._merge_trending_topics(results),
                "timestamp": datetime.now(UTC),
            }

        return {}

    async def _analyze_reddit(self) -> dict[str, Any]:
        """Analyze Reddit sentiment from relevant subreddits"""
        subreddits = ["wallstreetbets", "stocks", "options", "investing"]
        posts_analyzed = 0
        sentiments = []
        entities_mentioned = defaultdict(int)

        try:
            for subreddit_name in subreddits:
                subreddit = self.reddit_client.subreddit(subreddit_name)

                # Get hot posts
                for post in subreddit.hot(limit=25):
                    # Combine title and selftext
                    text = f"{post.title} {post.selftext}"

                    # Skip if too short
                    if len(text) < 50:
                        continue

                    # Analyze sentiment
                    sentiment = await self._analyze_text_sentiment(text, "reddit")
                    sentiments.append(sentiment.value * (1 + np.log1p(post.score) / 10))

                    # Extract entities
                    entities = await self._extract_entities(text)
                    for entity in entities:
                        entities_mentioned[entity] += 1

                    posts_analyzed += 1

                    # Analyze top comments
                    post.comments.replace_more(limit=0)
                    for comment in post.comments.list()[:10]:
                        if comment.score > 5:
                            comment_sentiment = await self._analyze_text_sentiment(
                                comment.body, "reddit_comment"
                            )
                            sentiments.append(
                                comment_sentiment.value * 0.5
                            )  # Lower weight

            return {
                "sentiment": np.mean(sentiments) if sentiments else 0.0,
                "posts_analyzed": posts_analyzed,
                "top_entities": sorted(
                    entities_mentioned.items(), key=lambda x: x[1], reverse=True
                )[:10],
                "confidence": min(
                    posts_analyzed / 50, 1.0
                ),  # Confidence based on sample size
            }

        except Exception as e:
            self.logger.error("Reddit analysis error: %s", e)
            return {}

    async def _analyze_twitter(self) -> dict[str, Any]:
        """Analyze Twitter/X sentiment for market-related tweets"""
        queries = ["$TRAD", "stock market", "Federal Reserve", "S&P500"]
        tweets_analyzed = 0
        sentiments = []

        try:
            for query in queries:
                tweets = self.twitter_client.search_recent_tweets(
                    query=query,
                    max_results=100,
                    tweet_fields=["author_id", "created_at", "public_metrics"],
                )

                if tweets.data:
                    for tweet in tweets.data:
                        # Analyze sentiment
                        sentiment = await self._analyze_text_sentiment(
                            tweet.text, "twitter"
                        )

                        # Weight by engagement
                        metrics = tweet.public_metrics
                        engagement = metrics["retweet_count"] + metrics["like_count"]
                        weight = 1 + np.log1p(engagement) / 10

                        sentiments.append(sentiment.value * weight)
                        tweets_analyzed += 1

            return {
                "sentiment": np.mean(sentiments) if sentiments else 0.0,
                "tweets_analyzed": tweets_analyzed,
                "confidence": min(tweets_analyzed / 200, 1.0),
            }

        except Exception as e:
            self.logger.error("Twitter analysis error: %s", e)
            return {}

    # ==========================================================================
    # ENTITY TRACKING
    # ==========================================================================

    async def _extract_entities(self, text: str) -> list[str]:
        """Extract named entities from text"""
        entities = set()

        try:
            # Use NER pipeline
            ner_results = self.pipelines["ner"](text)

            for entity in ner_results:
                if entity["entity_group"] in ["ORG", "PER"]:
                    entities.add(entity["word"])

            # Also check for known entities
            for _category, entity_list in ENTITY_CATEGORIES.items():
                for entity in entity_list:
                    if entity.lower() in text.lower():
                        entities.add(entity)

            return list(entities)

        except Exception as e:
            self.logger.error("Entity extraction error: %s", e)
            return []

    def _update_entity_sentiment(self, entity: str, sentiment: float, source: str):
        """Update sentiment tracking for specific entity"""
        # Determine entity type
        entity_type = "unknown"
        for category, entities in ENTITY_CATEGORIES.items():
            if entity in entities:
                entity_type = category
                break

        # Create or update entity sentiment
        if entity not in self.entity_sentiments:
            self.entity_sentiments[entity] = EntitySentiment(
                entity_name=entity, entity_type=entity_type
            )

        # Add new sentiment score
        score = SentimentScore(
            value=sentiment,
            confidence=0.8,
            source=source,
            text_snippet="",
            timestamp=datetime.now(UTC),
            entities=[entity],
        )

        self.entity_sentiments[entity].sentiment_scores.append(score)
        self.entity_sentiments[entity].mention_count += 1
        self.entity_sentiments[entity].last_updated = datetime.now(UTC)

    # ==========================================================================
    # CORE SENTIMENT ANALYSIS
    # ==========================================================================

    async def _analyze_text_sentiment(self, text: str, source: str) -> SentimentScore:
        """Analyze sentiment of text using appropriate model"""
        try:
            # Clean text
            text = self._clean_text(text)

            if not text:
                return SentimentScore(0.0, 0.0, source, "", datetime.now(UTC))

            # Choose model based on source
            if source in ["federal_reserve", "earnings_call", "news"]:
                # Use FinBERT for financial text
                sentiment = await self._finbert_sentiment(text)
            elif source in ["twitter", "reddit"]:
                # Use RoBERTa for social media
                sentiment = await self._roberta_sentiment(text)
            else:
                # Use TextBlob as fallback
                sentiment = TextBlob(text).sentiment.polarity
                confidence = min(abs(sentiment), 1.0)
                sentiment = SentimentScore(
                    sentiment, confidence, source, text[:100], datetime.now(UTC)
                )

            return sentiment

        except Exception as e:
            self.logger.error("Sentiment analysis error: %s", e)
            return SentimentScore(0.0, 0.0, source, "", datetime.now(UTC))

    async def _finbert_sentiment(self, text: str) -> SentimentScore:
        """Analyze sentiment using FinBERT"""
        # Truncate to model max length
        max_length = 512
        self.tokenizers["finbert"].encode(
            text, truncation=True, max_length=max_length
        )

        # Run model
        with torch.no_grad():
            inputs = self.tokenizers["finbert"](
                text,
                return_tensors="pt",
                truncation=True,
                max_length=max_length,
                padding=True,
            ).to(self.device)

            outputs = self.models["finbert"](**inputs)
            predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)

            # FinBERT outputs: [positive, negative, neutral]
            positive = predictions[0][0].item()
            negative = predictions[0][1].item()
            neutral = predictions[0][2].item()

            # Convert to single sentiment score
            sentiment_value = positive - negative
            confidence = 1.0 - neutral

            return SentimentScore(
                value=sentiment_value,
                confidence=confidence,
                source="finbert",
                text_snippet=text[:100],
                timestamp=datetime.now(UTC),
            )

    async def _roberta_sentiment(self, text: str) -> SentimentScore:
        """Analyze sentiment using RoBERTa"""
        result = self.pipelines["roberta"](text[:512])[0]

        # Map label to sentiment value
        label_map = {"POSITIVE": 1.0, "NEGATIVE": -1.0, "NEUTRAL": 0.0}

        sentiment_value = label_map.get(result["label"], 0.0)
        confidence = result["score"]

        return SentimentScore(
            value=sentiment_value,
            confidence=confidence,
            source="roberta",
            text_snippet=text[:100],
            timestamp=datetime.now(UTC),
        )

    def _clean_text(self, text: str) -> str:
        """Clean text for analysis"""
        # Remove URLs
        text = re.sub(r"http\S+|www.\S+", "", text)

        # Remove mentions and hashtags for general sentiment
        text = re.sub(r"@\w+|#\w+", "", text)

        # Remove excessive whitespace
        text = " ".join(text.split())

        return text.strip()

    # ==========================================================================
    # TOPIC MODELING
    # ==========================================================================

    def _extract_topics(self, text: str, num_topics: int = 5) -> list[str]:
        """Extract main topics from text using LDA"""
        try:
            # Tokenize and clean
            tokens = word_tokenize(text.lower())
            stop_words = set(stopwords.words("english"))
            tokens = [
                t for t in tokens if t.isalpha() and t not in stop_words and len(t) > 3
            ]

            if len(tokens) < 20:
                return []

            # Create document-term matrix
            vectorizer = TfidfVectorizer(max_features=50, ngram_range=(1, 2))
            doc_term_matrix = vectorizer.fit_transform([" ".join(tokens)])

            # LDA topic modeling
            lda = LatentDirichletAllocation(
                n_components=min(num_topics, 5), random_state=42
            )
            lda.fit(doc_term_matrix)

            # Extract topics
            feature_names = vectorizer.get_feature_names_out()
            topics = []

            for _topic_idx, topic in enumerate(lda.components_):
                top_features_idx = topic.argsort()[-5:][::-1]
                top_features = [feature_names[i] for i in top_features_idx]
                topics.append(" ".join(top_features[:3]))

            return topics

        except Exception as e:
            self.logger.error("Topic extraction error: %s", e)
            return []

    # ==========================================================================
    # EVENT DETECTION
    # ==========================================================================

    def _check_earnings_event(self, analysis: dict[str, Any]) -> MarketEvent | None:
        """Check if earnings analysis represents significant event"""
        sentiment = analysis["overall_sentiment"]
        guidance = analysis.get("guidance_sentiment", 0)

        # Check for significant surprise
        if abs(sentiment) > 0.5 or abs(guidance) > 0.6:
            impact = min(abs(sentiment) + abs(guidance) / 2, 1.0)

            return MarketEvent(
                event_type="earnings_announcement",
                description=f"{analysis['company']} {analysis['quarter']} earnings",
                impact_score=impact,
                sentiment=sentiment,
                entities=[analysis["company"]],
                source="earnings_call",
                timestamp=datetime.now(UTC),
                predicted_duration=timedelta(days=1),
                confidence=analysis["confidence"],
            )

        return None

    # ==========================================================================
    # AUDIO TRANSCRIPTION
    # ==========================================================================

    async def transcribe_audio(self, audio_file: str) -> str:
        """Transcribe audio file (e.g., Fed speech, earnings call)"""
        if not self.whisper_model:
            self.logger.warning("Whisper model not available")
            return ""

        try:
            result = self.whisper_model.transcribe(audio_file)
            return result["text"]
        except Exception as e:
            self.logger.error("Transcription error: %s", e)
            return ""

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================

    async def get_market_sentiment(self) -> SentimentReport:
        """Get comprehensive current market sentiment"""
        try:
            # Analyze recent data from all sources
            tasks = []

            # Social media
            tasks.append(self.analyze_social_media())

            # Recent news (mock data for example)
            tasks.append(
                self.analyze_multilingual_news(
                    [
                        {
                            "text": "Market reaches new highs...",
                            "language": "en",
                            "source": "reuters",
                        },
                        {
                            "text": "Inflation concerns grow...",
                            "language": "en",
                            "source": "bloomberg",
                        },
                    ]
                )
            )

            # Gather results
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Calculate overall sentiment
            sentiments = []
            weights = []

            for _i, result in enumerate(results):
                if isinstance(result, dict) and "overall_sentiment" in result:
                    sentiments.append(result["overall_sentiment"])
                    weights.append(1.0)  # Could use source weights

            if sentiments:
                overall_sentiment = np.average(sentiments, weights=weights)
            else:
                overall_sentiment = 0.0

            # Get top entities
            top_entities = sorted(
                [(k, v.current_sentiment) for k, v in self.entity_sentiments.items()],
                key=lambda x: abs(x[1]),
                reverse=True,
            )[:10]

            # Determine regime
            if overall_sentiment > POSITIVE_THRESHOLD:
                regime = "bullish"
            elif overall_sentiment < NEGATIVE_THRESHOLD:
                regime = "bearish"
            elif abs(overall_sentiment) < 0.1:
                regime = "neutral"
            else:
                regime = "mixed"

            # Create report
            report = SentimentReport(
                overall_sentiment=overall_sentiment,
                sentiment_distribution={
                    "positive": len([s for s in sentiments if s > 0])
                    / max(len(sentiments), 1),
                    "negative": len([s for s in sentiments if s < 0])
                    / max(len(sentiments), 1),
                    "neutral": len([s for s in sentiments if abs(s) < 0.1])
                    / max(len(sentiments), 1),
                },
                top_entities=top_entities,
                detected_events=list(self.recent_events)[-10:],
                sentiment_momentum=self._calculate_momentum(),
                regime=regime,
                confidence=0.8,
                key_themes=self._get_recent_themes(),
                warnings=self._generate_warnings(),
            )

            return report

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "get_market_sentiment"})
            return SentimentReport(
                overall_sentiment=0.0,
                sentiment_distribution={},
                top_entities=[],
                detected_events=[],
                sentiment_momentum=0.0,
                regime="unknown",
                confidence=0.0,
                key_themes=[],
                warnings=["Error generating sentiment report"],
            )

    def _calculate_momentum(self) -> float:
        """Calculate sentiment momentum"""
        if len(self.sentiment_history) < 10:
            return 0.0

        recent = list(self.sentiment_history)[-5:]
        older = list(self.sentiment_history)[-10:-5]

        recent_avg = np.mean([s.value for s in recent])
        older_avg = np.mean([s.value for s in older])

        return recent_avg - older_avg

    def _get_recent_themes(self) -> list[str]:
        """Get recent dominant themes"""
        themes = defaultdict(int)

        for event in list(self.recent_events)[-20:]:
            if event.event_type:
                themes[event.event_type] += 1

        return [k for k, v in sorted(themes.items(), key=lambda x: x[1], reverse=True)][
            :5
        ]

    def _generate_warnings(self) -> list[str]:
        """Generate sentiment-based warnings"""
        warnings = []

        # Check for rapid sentiment shifts
        if abs(self._calculate_momentum()) > 0.5:
            warnings.append("Rapid sentiment shift detected")

        # Check for divergent sentiments
        entity_sentiments = [
            e.current_sentiment for e in self.entity_sentiments.values()
        ]
        if entity_sentiments and np.std(entity_sentiments) > 0.5:
            warnings.append("High sentiment divergence across entities")

        # Check for high-impact events
        recent_high_impact = [e for e in self.recent_events if e.impact_score > 0.8]
        if recent_high_impact:
            warnings.append(f"High-impact event: {recent_high_impact[-1].description}")

        return warnings


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_module_instance: EnhancedSentimentAnalysisAgent | None = None


def create_sentiment_analysis_agent(
    config: dict[str, Any] | None = None,
) -> EnhancedSentimentAnalysisAgent:
    """Factory function to create sentiment analysis agent"""
    global _module_instance
    if _module_instance is None:
        _module_instance = EnhancedSentimentAnalysisAgent(config)
    return _module_instance


def get_sentiment_analysis_agent() -> EnhancedSentimentAnalysisAgent | None:
    """Get existing instance"""
    return _module_instance


# ==============================================================================
# AGENT REGISTRATION UPDATE
# ==============================================================================
# Update the existing TradovX11_SentimentAnalysisAgent to use enhanced version
TradovX11_SentimentAnalysisAgent = EnhancedSentimentAnalysisAgent


# ==============================================================================
# COMMAND LINE INTERFACE
# ==============================================================================
async def main():
    """Test sentiment analysis functionality"""
    import argparse

    parser = argparse.ArgumentParser(description="Enhanced Sentiment Analysis Testing")
    parser.add_argument("--earnings", type=str, help="Analyze earnings transcript file")
    parser.add_argument("--fed", type=str, help="Analyze Fed communication file")
    parser.add_argument("--social", action="store_true", help="Analyze social media")
    parser.add_argument(
        "--report", action="store_true", help="Generate sentiment report"
    )
    args = parser.parse_args()

    # Create agent with mock config
    config = {
        # Add your API keys here for testing
        # 'reddit_client_id': 'your_id',
        # 'reddit_secret': 'your_secret',
        # 'twitter_bearer_token': 'your_token'
    }

    agent = create_sentiment_analysis_agent(config)

    if args.earnings:
        logging.info("\n=== Analyzing Earnings Call ===")
        with open(args.earnings) as f:
            transcript = f.read()

        analysis = await agent.analyze_earnings_call(
            transcript, company="Test Corp", quarter="Q2 2025"
        )

        logging.info(f"Overall Sentiment: {analysis.get('overall_sentiment', 0):.3f}")
        logging.info(f"Guidance Sentiment: {analysis.get('guidance_sentiment', 0):.3f}")
        logging.info("Main Topics: %s", analysis.get('main_topics', []))
        logging.info("\nKey Quotes:")
        for quote in analysis.get("key_quotes", [])[:3]:
            logging.info(f"- {quote['text'][:100]}... (sentiment: {quote['sentiment']:.2f})")

    if args.fed:
        logging.info("\n=== Analyzing Fed Communication ===")
        with open(args.fed) as f:
            text = f.read()

        analysis = await agent.analyze_fed_communication(
            text, comm_type="FOMC_statement", speaker="Jerome Powell"
        )

        logging.info(
            f"Policy Stance: {analysis.get('policy_stance', 0):.3f} (-1 dovish to 1 hawkish)"
        )
        logging.info(f"Overall Sentiment: {analysis.get('overall_sentiment', 0):.3f}")
        logging.info("\nTopic Analysis:")
        for topic, data in analysis.get("topics", {}).items():
            if data["mentioned"]:
                logging.info(
                    f"- {topic}: sentiment={data['sentiment']:.2f}, prominence={data['prominence']:.2%}"  # noqa: E501
                )
        logging.info("\nRate Implications: %s", analysis.get('rate_implications', {}))

    if args.social:
        logging.info("\n=== Analyzing Social Media ===")
        analysis = await agent.analyze_social_media(["reddit", "twitter"])

        logging.info(f"Overall Sentiment: {analysis.get('overall_sentiment', 0):.3f}")
        logging.info("\nPlatform Sentiments:")
        for platform, data in analysis.get("platform_sentiments", {}).items():
            logging.info(f"- {platform}: {data.get('sentiment', 0):.3f}")

    if args.report:
        logging.info("\n=== Market Sentiment Report ===")
        report = await agent.get_market_sentiment()

        logging.info(f"Overall Market Sentiment: {report.overall_sentiment:.3f}")
        logging.info("Sentiment Regime: %s", report.regime)
        logging.info(f"Momentum: {report.sentiment_momentum:.3f}")
        logging.info(f"Confidence: {report.confidence:.2%}")

        logging.info("\nTop Entities:")
        for entity, sentiment in report.top_entities[:5]:
            logging.info(f"- {entity}: {sentiment:.3f}")

        logging.info("\nRecent Events:")
        for event in report.detected_events[-3:]:
            logging.info(
                f"- {event.event_type}: {event.description} (impact: {event.impact_score:.2f})"
            )

        if report.warnings:
            logging.info("\nWarnings:")
            for warning in report.warnings:
                logging.info("⚠️  %s", warning)


if __name__ == "__main__":
    asyncio.run(main())
