"""
Natural Language Module

Handles natural language processing, understanding, and generation for the AI agent.
"""

import asyncio
import json
import logging
import re
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import uuid
import math


class Language(Enum):
    """Supported languages."""
    
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    CHINESE = "zh"
    JAPANESE = "ja"
    KOREAN = "ko"
    RUSSIAN = "ru"
    ARABIC = "ar"
    PORTUGUESE = "pt"


class IntentType(Enum):
    """Types of intents that can be recognized."""
    
    GREETING = "greeting"
    FAREWELL = "farewell"
    QUESTION = "question"
    COMMAND = "command"
    REQUEST = "request"
    INFORM = "inform"
    CONFIRM = "confirm"
    DENY = "deny"
    THANKS = "thanks"
    APOLOGY = "apology"
    COMPLIMENT = "compliment"
    COMPLAINT = "complaint"
    UNKNOWN = "unknown"


class Sentiment(Enum):
    """Sentiment categories."""
    
    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"


class EntityType(Enum):
    """Types of entities that can be extracted."""
    
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    DATE = "date"
    TIME = "time"
    MONEY = "money"
    PHONE = "phone"
    EMAIL = "email"
    URL = "url"
    NUMBER = "number"
    PERCENTAGE = "percentage"
    PRODUCT = "product"
    EVENT = "event"
    CUSTOM = "custom"


@dataclass
class Entity:
    """An extracted entity from text."""
    
    text: str
    entity_type: EntityType
    start_pos: int
    end_pos: int
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dictionary."""
        data = asdict(self)
        data['entity_type'] = self.entity_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Entity':
        """Create entity from dictionary."""
        if 'entity_type' in data and isinstance(data['entity_type'], str):
            data['entity_type'] = EntityType(data['entity_type'])
        return cls(**data)


@dataclass
class Intent:
    """A recognized intent from text."""
    
    intent_type: IntentType
    confidence: float = 0.0
    parameters: Dict[str, Any] = field(default_factory=dict)
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert intent to dictionary."""
        data = asdict(self)
        data['intent_type'] = self.intent_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Intent':
        """Create intent from dictionary."""
        if 'intent_type' in data and isinstance(data['intent_type'], str):
            data['intent_type'] = IntentType(data['intent_type'])
        return cls(**data)


@dataclass
class NLUResult:
    """Result of natural language understanding."""
    
    text: str
    language: Language
    intent: Intent
    entities: List[Entity] = field(default_factory=list)
    sentiment: Sentiment = Sentiment.NEUTRAL
    sentiment_score: float = 0.0
    confidence: float = 0.0
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert NLU result to dictionary."""
        data = asdict(self)
        data['language'] = self.language.value
        data['intent'] = self.intent.to_dict()
        data['entities'] = [entity.to_dict() for entity in self.entities]
        data['sentiment'] = self.sentiment.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NLUResult':
        """Create NLU result from dictionary."""
        if 'language' in data and isinstance(data['language'], str):
            data['language'] = Language(data['language'])
        if 'intent' in data:
            data['intent'] = Intent.from_dict(data['intent'])
        if 'entities' in data:
            data['entities'] = [Entity.from_dict(entity) for entity in data['entities']]
        if 'sentiment' in data and isinstance(data['sentiment'], str):
            data['sentiment'] = Sentiment(data['sentiment'])
        return cls(**data)


@dataclass
class NLGContext:
    """Context for natural language generation."""
    
    intent: IntentType
    entities: List[Entity] = field(default_factory=list)
    sentiment: Sentiment = Sentiment.NEUTRAL
    formality: float = 0.5  # 0.0 (informal) to 1.0 (formal)
    creativity: float = 0.5  # 0.0 (conservative) to 1.0 (creative)
    length_preference: str = "medium"  # short, medium, long
    style: str = "neutral"  # neutral, friendly, professional, casual
    previous_context: List[str] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        data = asdict(self)
        data['intent'] = self.intent.value
        data['entities'] = [entity.to_dict() for entity in self.entities]
        data['sentiment'] = self.sentiment.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NLGContext':
        """Create context from dictionary."""
        if 'intent' in data and isinstance(data['intent'], str):
            data['intent'] = IntentType(data['intent'])
        if 'entities' in data:
            data['entities'] = [Entity.from_dict(entity) for entity in data['entities']]
        if 'sentiment' in data and isinstance(data['sentiment'], str):
            data['sentiment'] = Sentiment(data['sentiment'])
        return cls(**data)


class NaturalLanguageProcessor:
    """Handles natural language processing tasks."""
    
    def __init__(self, config):
        """Initialize natural language processor."""
        self.config = config
        self.logger = logging.getLogger("natural_language")
        
        # Language models and processors
        self._language_detectors = {}
        self._intent_classifiers = {}
        self._entity_extractors = {}
        self._sentiment_analyzers = {}
        self._text_generators = {}
        
        # Templates and patterns
        self._intent_patterns = self._initialize_intent_patterns()
        self._entity_patterns = self._initialize_entity_patterns()
        self._response_templates = self._initialize_response_templates()
        
        # Vocabulary and knowledge
        self._vocabulary = {}
        self._synonyms = {}
        self._antonyms = {}
        self._word_embeddings = {}
        
        # Statistics
        self._total_processed = 0
        self._total_generated = 0
        self._average_processing_time = 0.0
        self._language_distribution = {}
        
        # Caching
        self._nlu_cache = {}
        self._nlg_cache = {}
        self._cache_ttl = timedelta(hours=1)
    
    async def initialize(self) -> None:
        """Initialize the natural language processor."""
        try:
            # Load language models
            await self._load_language_models()
            
            # Initialize processors
            await self._initialize_processors()
            
            # Load vocabulary
            await self._load_vocabulary()
            
            self.logger.info("Natural language processor initialized")
            
        except Exception as e:
            self.logger.error(f"Error initializing natural language processor: {e}")
            raise
    
    async def understand_text(self, text: str, language: Optional[Language] = None) -> NLUResult:
        """Understand natural language text."""
        try:
            start_time = datetime.now()
            
            # Check cache
            cache_key = f"{text}:{language.value if language else 'auto'}"
            if cache_key in self._nlu_cache:
                cached_result = self._nlu_cache[cache_key]
                if datetime.now() - cached_result['timestamp'] < self._cache_ttl:
                    return cached_result['result']
            
            # Detect language if not provided
            if not language:
                language = await self._detect_language(text)
            
            # Preprocess text
            processed_text = await self._preprocess_text(text, language)
            
            # Extract intent
            intent = await self._extract_intent(processed_text, language)
            
            # Extract entities
            entities = await self._extract_entities(processed_text, language)
            
            # Analyze sentiment
            sentiment, sentiment_score = await self._analyze_sentiment(processed_text, language)
            
            # Calculate overall confidence
            confidence = await self._calculate_confidence(intent, entities, sentiment_score)
            
            # Create result
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds() * 1000
            
            result = NLUResult(
                text=text,
                language=language,
                intent=intent,
                entities=entities,
                sentiment=sentiment,
                sentiment_score=sentiment_score,
                confidence=confidence,
                processing_time_ms=processing_time
            )
            
            # Cache result
            self._nlu_cache[cache_key] = {
                'result': result,
                'timestamp': datetime.now()
            }
            
            # Update statistics
            self._total_processed += 1
            self._update_processing_stats(processing_time)
            self._update_language_distribution(language)
            
            self.logger.debug(f"Processed text: {text[:50]}...")
            return result
            
        except Exception as e:
            self.logger.error(f"Error understanding text: {e}")
            # Return fallback result
            return NLUResult(
                text=text,
                language=language or Language.ENGLISH,
                intent=Intent(IntentType.UNKNOWN, 0.0),
                sentiment=Sentiment.NEUTRAL,
                confidence=0.0
            )
    
    async def generate_response(
        self,
        context: NLGContext,
        max_length: int = 500,
        num_responses: int = 1
    ) -> List[str]:
        """Generate natural language responses."""
        try:
            # Check cache
            cache_key = f"{context.to_dict()}:{max_length}:{num_responses}"
            if cache_key in self._nlg_cache:
                cached_result = self._nlg_cache[cache_key]
                if datetime.now() - cached_result['timestamp'] < self._cache_ttl:
                    return cached_result['responses']
            
            # Generate responses
            responses = []
            
            for _ in range(num_responses):
                response = await self._generate_single_response(context, max_length)
                if response:
                    responses.append(response)
            
            # Cache responses
            self._nlg_cache[cache_key] = {
                'responses': responses,
                'timestamp': datetime.now()
            }
            
            # Update statistics
            self._total_generated += len(responses)
            
            self.logger.debug(f"Generated {len(responses)} responses")
            return responses
            
        except Exception as e:
            self.logger.error(f"Error generating response: {e}")
            # Return fallback responses
            return await self._generate_fallback_responses(context)
    
    async def translate_text(
        self,
        text: str,
        source_language: Language,
        target_language: Language
    ) -> str:
        """Translate text from source to target language."""
        try:
            # In a real implementation, use translation service
            # For now, return a placeholder
            return f"[Translated from {source_language.value} to {target_language.value}]: {text}"
            
        except Exception as e:
            self.logger.error(f"Error translating text: {e}")
            return text
    
    async def summarize_text(
        self,
        text: str,
        max_sentences: int = 3,
        language: Optional[Language] = None
    ) -> str:
        """Summarize text."""
        try:
            if not language:
                language = await self._detect_language(text)
            
            # Simple extractive summarization
            sentences = await self._split_sentences(text, language)
            
            if len(sentences) <= max_sentences:
                return text
            
            # Score sentences based on importance
            sentence_scores = []
            for sentence in sentences:
                score = await self._score_sentence(sentence, text)
                sentence_scores.append((sentence, score))
            
            # Sort by score and take top sentences
            sentence_scores.sort(key=lambda x: x[1], reverse=True)
            top_sentences = [s[0] for s in sentence_scores[:max_sentences]]
            
            # Reorder by original position
            summary_sentences = []
            for sentence in sentences:
                if sentence in top_sentences:
                    summary_sentences.append(sentence)
            
            return " ".join(summary_sentences)
            
        except Exception as e:
            self.logger.error(f"Error summarizing text: {e}")
            return text[:200] + "..." if len(text) > 200 else text
    
    async def extract_keywords(
        self,
        text: str,
        max_keywords: int = 10,
        language: Optional[Language] = None
    ) -> List[str]:
        """Extract keywords from text."""
        try:
            if not language:
                language = await self._detect_language(text)
            
            # Simple keyword extraction using TF-IDF
            words = await self._tokenize(text, language)
            
            # Filter stopwords and short words
            filtered_words = [
                word.lower() for word in words
                if len(word) > 2 and not await self._is_stopword(word.lower(), language)
            ]
            
            # Count word frequencies
            word_freq = {}
            for word in filtered_words:
                word_freq[word] = word_freq.get(word, 0) + 1
            
            # Sort by frequency and return top keywords
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            keywords = [word for word, _ in sorted_words[:max_keywords]]
            
            return keywords
            
        except Exception as e:
            self.logger.error(f"Error extracting keywords: {e}")
            return []
    
    async def get_language_stats(self) -> Dict[str, Any]:
        """Get language processing statistics."""
        try:
            stats = {
                'total_processed': self._total_processed,
                'total_generated': self._total_generated,
                'average_processing_time_ms': self._average_processing_time,
                'language_distribution': self._language_distribution.copy(),
                'cache_size': {
                    'nlu_cache': len(self._nlu_cache),
                    'nlg_cache': len(self._nlg_cache)
                },
                'supported_languages': [lang.value for lang in Language],
                'supported_intents': [intent.value for intent in IntentType],
                'supported_entities': [entity.value for entity in EntityType]
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting language stats: {e}")
            return {}
    
    async def _load_language_models(self) -> None:
        """Load language models."""
        # In a real implementation, load actual language models
        for language in Language:
            self._language_detectors[language] = True  # Placeholder
    
    async def _initialize_processors(self) -> None:
        """Initialize NLP processors."""
        # Initialize intent classifiers
        for language in Language:
            self._intent_classifiers[language] = True  # Placeholder
        
        # Initialize entity extractors
        for language in Language:
            self._entity_extractors[language] = True  # Placeholder
        
        # Initialize sentiment analyzers
        for language in Language:
            self._sentiment_analyzers[language] = True  # Placeholder
        
        # Initialize text generators
        for language in Language:
            self._text_generators[language] = True  # Placeholder
    
    async def _load_vocabulary(self) -> None:
        """Load vocabulary and linguistic resources."""
        # In a real implementation, load actual vocabulary
        self._vocabulary = {
            'en': ['hello', 'world', 'help', 'please', 'thank', 'you'],
            'es': ['hola', 'mundo', 'ayuda', 'por', 'favor', 'gracias'],
            'fr': ['bonjour', 'monde', 'aide', 's\'il', 'vous', 'plaît'],
        }
    
    async def _detect_language(self, text: str) -> Language:
        """Detect the language of text."""
        # Simple language detection based on common words
        text_lower = text.lower()
        
        language_scores = {}
        for language in Language:
            if language.value in self._vocabulary:
                vocab = self._vocabulary[language.value]
                score = sum(1 for word in vocab if word in text_lower)
                language_scores[language] = score
        
        if language_scores:
            best_language = max(language_scores, key=language_scores.get)
            if language_scores[best_language] > 0:
                return best_language
        
        return Language.ENGLISH  # Default to English
    
    async def _preprocess_text(self, text: str, language: Language) -> str:
        """Preprocess text for NLP."""
        # Convert to lowercase
        processed = text.lower()
        
        # Remove extra whitespace
        processed = re.sub(r'\s+', ' ', processed).strip()
        
        # Remove special characters (keep basic punctuation)
        processed = re.sub(r'[^\w\s\.,!?;:]', '', processed)
        
        return processed
    
    async def _extract_intent(self, text: str, language: Language) -> Intent:
        """Extract intent from text."""
        # Pattern-based intent recognition
        text_lower = text.lower()
        
        intent_scores = {}
        
        for intent_type, patterns in self._intent_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    score += 1
            intent_scores[intent_type] = score
        
        if intent_scores:
            best_intent = max(intent_scores, key=intent_scores.get)
            confidence = min(1.0, intent_scores[best_intent] / len(self._intent_patterns[best_intent]))
            
            if confidence > 0.1:
                return Intent(best_intent, confidence)
        
        return Intent(IntentType.UNKNOWN, 0.0)
    
    async def _extract_entities(self, text: str, language: Language) -> List[Entity]:
        """Extract entities from text."""
        entities = []
        
        # Pattern-based entity extraction
        for entity_type, patterns in self._entity_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    entity = Entity(
                        text=match.group(),
                        entity_type=entity_type,
                        start_pos=match.start(),
                        end_pos=match.end(),
                        confidence=0.8  # Default confidence for pattern matches
                    )
                    entities.append(entity)
        
        # Remove overlapping entities (keep longer ones)
        entities = self._remove_overlapping_entities(entities)
        
        return entities
    
    async def _analyze_sentiment(self, text: str, language: Language) -> Tuple[Sentiment, float]:
        """Analyze sentiment of text."""
        # Simple sentiment analysis based on keywords
        positive_words = ['good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic', 'love', 'like', 'happy', 'pleased']
        negative_words = ['bad', 'terrible', 'awful', 'horrible', 'hate', 'dislike', 'sad', 'angry', 'frustrated', 'disappointed']
        
        text_lower = text.lower()
        words = text_lower.split()
        
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        
        total_sentiment_words = positive_count + negative_count
        
        if total_sentiment_words == 0:
            return Sentiment.NEUTRAL, 0.0
        
        # Calculate sentiment score (-1 to 1)
        sentiment_score = (positive_count - negative_count) / total_sentiment_words
        
        # Convert to sentiment category
        if sentiment_score > 0.6:
            sentiment = Sentiment.VERY_POSITIVE
        elif sentiment_score > 0.2:
            sentiment = Sentiment.POSITIVE
        elif sentiment_score > -0.2:
            sentiment = Sentiment.NEUTRAL
        elif sentiment_score > -0.6:
            sentiment = Sentiment.NEGATIVE
        else:
            sentiment = Sentiment.VERY_NEGATIVE
        
        return sentiment, sentiment_score
    
    async def _calculate_confidence(
        self,
        intent: Intent,
        entities: List[Entity],
        sentiment_score: float
    ) -> float:
        """Calculate overall confidence."""
        # Weighted average of component confidences
        intent_weight = 0.5
        entity_weight = 0.3
        sentiment_weight = 0.2
        
        entity_confidence = sum(e.confidence for e in entities) / len(entities) if entities else 0.0
        sentiment_confidence = abs(sentiment_score)
        
        overall_confidence = (
            intent.confidence * intent_weight +
            entity_confidence * entity_weight +
            sentiment_confidence * sentiment_weight
        )
        
        return min(1.0, overall_confidence)
    
    async def _generate_single_response(self, context: NLGContext, max_length: int) -> str:
        """Generate a single response."""
        # Template-based response generation
        templates = self._response_templates.get(context.intent, [])
        
        if not templates:
            return await self._generate_fallback_response(context)
        
        # Select template based on context
        template = await self._select_template(templates, context)
        
        # Fill template with entities
        response = await self._fill_template(template, context)
        
        # Adjust length if needed
        if len(response) > max_length:
            response = response[:max_length-3] + "..."
        
        return response
    
    async def _select_template(self, templates: List[str], context: NLGContext) -> str:
        """Select appropriate template based on context."""
        # Simple selection based on formality
        if context.formality > 0.7:
            # Formal templates
            formal_templates = [t for t in templates if "formal" in t.lower() or "please" in t.lower()]
            if formal_templates:
                return formal_templates[0]
        elif context.formality < 0.3:
            # Informal templates
            informal_templates = [t for t in templates if "hey" in t.lower() or "hi" in t.lower()]
            if informal_templates:
                return informal_templates[0]
        
        # Default: first template
        return templates[0]
    
    async def _fill_template(self, template: str, context: NLGContext) -> str:
        """Fill template with entities and context."""
        response = template
        
        # Replace entity placeholders
        for entity in context.entities:
            placeholder = f"{{{entity.entity_type.value}}}"
            if placeholder in response:
                response = response.replace(placeholder, entity.text)
        
        # Adjust based on sentiment
        if context.sentiment == Sentiment.POSITIVE:
            response = response.replace("{sentiment}", "😊")
        elif context.sentiment == Sentiment.NEGATIVE:
            response = response.replace("{sentiment}", "😔")
        else:
            response = response.replace("{sentiment}", "")
        
        return response
    
    async def _generate_fallback_responses(self, context: NLGContext) -> List[str]:
        """Generate fallback responses."""
        fallbacks = [
            "I understand your request.",
            "I'm processing your input.",
            "Thank you for your message.",
            "I'm here to help."
        ]
        
        return fallbacks[:1]  # Return one fallback
    
    async def _generate_fallback_response(self, context: NLGContext) -> str:
        """Generate a single fallback response."""
        fallbacks = [
            "I understand your request.",
            "I'm processing your input.",
            "Thank you for your message.",
            "I'm here to help."
        ]
        
        return fallbacks[0]
    
    async def _split_sentences(self, text: str, language: Language) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences
    
    async def _score_sentence(self, sentence: str, full_text: str) -> float:
        """Score sentence importance for summarization."""
        # Simple scoring based on length and keyword presence
        score = 0.0
        
        # Length score (prefer medium-length sentences)
        length = len(sentence.split())
        if 5 <= length <= 20:
            score += 0.5
        elif length > 20:
            score += 0.3
        
        # Keyword score
        keywords = await self.extract_keywords(full_text, max_keywords=5)
        keyword_count = sum(1 for keyword in keywords if keyword.lower() in sentence.lower())
        score += keyword_count * 0.2
        
        # Position score (earlier sentences get higher score)
        sentence_index = full_text.find(sentence)
        if sentence_index >= 0:
            position_score = 1.0 - (sentence_index / len(full_text))
            score += position_score * 0.3
        
        return score
    
    async def _tokenize(self, text: str, language: Language) -> List[str]:
        """Tokenize text into words."""
        # Simple tokenization
        tokens = re.findall(r'\b\w+\b', text.lower())
        return tokens
    
    async def _is_stopword(self, word: str, language: Language) -> bool:
        """Check if word is a stopword."""
        # Simple stopword list
        stopwords = {
            'en': ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'],
            'es': ['el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'y', 'o', 'pero', 'en', 'de', 'a', 'para', 'con', 'por', 'es', 'son', 'está', 'están', 'ser', 'estar', 'tener', 'ha', 'han', 'hacer', 'hace', 'hacen', 'este', 'esta', 'estos', 'estas', 'yo', 'tú', 'él', 'ella', 'nosotros', 'ellos'],
        }
        
        return word in stopwords.get(language.value, [])
    
    def _remove_overlapping_entities(self, entities: List[Entity]) -> List[Entity]:
        """Remove overlapping entities, keeping longer ones."""
        if not entities:
            return entities
        
        # Sort by start position, then by length (longer first)
        sorted_entities = sorted(entities, key=lambda e: (e.start_pos, -(e.end_pos - e.start_pos)))
        
        filtered_entities = []
        for entity in sorted_entities:
            # Check if entity overlaps with any already selected entity
            overlaps = False
            for selected in filtered_entities:
                if (entity.start_pos < selected.end_pos and 
                    entity.end_pos > selected.start_pos):
                    overlaps = True
                    break
            
            if not overlaps:
                filtered_entities.append(entity)
        
        return filtered_entities
    
    def _update_processing_stats(self, processing_time: float) -> None:
        """Update processing time statistics."""
        if self._total_processed == 1:
            self._average_processing_time = processing_time
        else:
            # Running average
            alpha = 0.1  # Smoothing factor
            self._average_processing_time = (
                alpha * processing_time +
                (1 - alpha) * self._average_processing_time
            )
    
    def _update_language_distribution(self, language: Language) -> None:
        """Update language distribution statistics."""
        lang_code = language.value
        self._language_distribution[lang_code] = self._language_distribution.get(lang_code, 0) + 1
    
    def _initialize_intent_patterns(self) -> Dict[IntentType, List[str]]:
        """Initialize intent recognition patterns."""
        return {
            IntentType.GREETING: [
                r'\b(hello|hi|hey|good morning|good afternoon|good evening)\b',
                r'\b(hola|bonjour|guten tag|bonjourno|konnichiwa)\b'
            ],
            IntentType.FAREWELL: [
                r'\b(bye|goodbye|see you|farewell|take care)\b',
                r'\b(adiós|au revoir|auf wiedersehen|arrivederci|sayonara)\b'
            ],
            IntentType.QUESTION: [
                r'\b(what|when|where|why|how|who|which|whose)\b',
                r'\b\?'
            ],
            IntentType.COMMAND: [
                r'\b(do|make|create|delete|update|show|tell|give|send)\b',
                r'\b(please|can you|could you)\s+\w+'
            ],
            IntentType.REQUEST: [
                r'\b(can|could|would|will|may)\s+(you|please)\b',
                r'\b(need|want|require|looking for)\b'
            ],
            IntentType.THANKS: [
                r'\b(thank|thanks|gracias|merci|danke|arigato)\b',
                r'\b(appreciate|grateful)\b'
            ],
            IntentType.APOLOGY: [
                r'\b(sorry|apologize|excuse me|pardon|forgive)\b',
                r'\b(my bad|regret)\b'
            ],
            IntentType.CONFIRM: [
                r'\b(yes|yeah|yep|sure|absolutely|definitely|correct)\b',
                r'\b(agreed|confirmed|affirmative)\b'
            ],
            IntentType.DENY: [
                r'\b(no|nope|not|never|absolutely not)\b',
                r'\b(disagree|decline|refuse)\b'
            ]
        }
    
    def _initialize_entity_patterns(self) -> Dict[EntityType, List[str]]:
        """Initialize entity extraction patterns."""
        return {
            EntityType.EMAIL: [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            ],
            EntityType.PHONE: [
                r'\b\d{3}-\d{3}-\d{4}\b',
                r'\b\(\d{3}\)\s*\d{3}-\d{4}\b',
                r'\b\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
            ],
            EntityType.URL: [
                r'\bhttps?://[^\s<>"{}|\\^`\[\]]+\b',
                r'\bwww\.[^\s<>"{}|\\^`\[\]]+\b'
            ],
            EntityType.DATE: [
                r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
                r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',
                r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}\b'
            ],
            EntityType.TIME: [
                r'\b\d{1,2}:\d{2}\s*(am|pm)?\b',
                r'\b\d{1,2}\s*(am|pm)\b'
            ],
            EntityType.MONEY: [
                r'\$\d+(?:,\d{3})*(?:\.\d{2})?\b',
                r'\b\d+(?:,\d{3})*(?:\.\d{2})?\s*(dollars|euros|pounds|cents)\b'
            ],
            EntityType.NUMBER: [
                r'\b\d+(?:,\d{3})*(?:\.\d+)?\b'
            ],
            EntityType.PERCENTAGE: [
                r'\b\d+(?:\.\d+)?%\b',
                r'\b\d+(?:\.\d+)?\s*percent\b'
            ]
        }
    
    def _initialize_response_templates(self) -> Dict[IntentType, List[str]]:
        """Initialize response templates."""
        return {
            IntentType.GREETING: [
                "Hello! How can I help you today?",
                "Hi there! What can I do for you?",
                "Good day! How may I assist you?",
                "Hello! I'm here to help."
            ],
            IntentType.FAREWELL: [
                "Goodbye! Have a great day!",
                "See you later! Take care.",
                "Farewell! It was nice talking to you.",
                "Bye! Come back anytime."
            ],
            IntentType.QUESTION: [
                "That's a great question! Let me help you with that.",
                "I understand you're asking about {entity}. Here's what I know...",
                "Let me find the answer to your question.",
                "I'd be happy to help answer your question."
            ],
            IntentType.COMMAND: [
                "I'll help you {command} right away.",
                "Executing your command to {command}.",
                "Sure! I'll {command} for you.",
                "I'll take care of that {command} immediately."
            ],
            IntentType.REQUEST: [
                "I'd be happy to help with your request.",
                "Certainly! Let me assist you with that.",
                "I understand what you need. I'll help you.",
                "Your request is important. Let me handle it."
            ],
            IntentType.THANKS: [
                "You're welcome! I'm glad I could help.",
                "Happy to assist! Is there anything else?",
                "My pleasure! Don't hesitate to ask if you need more help.",
                "You're very welcome! It's my job to help."
            ],
            IntentType.APOLOGY: [
                "No problem at all! These things happen.",
                "That's quite alright! No need to apologize.",
                "Don't worry about it! Is there something I can help with?",
                "It's completely fine! How can I assist you?"
            ],
            IntentType.CONFIRM: [
                "Great! I'll proceed with that.",
                "Perfect! Let me take care of it.",
                "Excellent! I understand and will help.",
                "Wonderful! I'm on it."
            ],
            IntentType.DENY: [
                "I understand. Let me suggest an alternative.",
                "No problem! Is there something else I can help with?",
                "I see. Perhaps we could try a different approach?",
                "Understood. Let me know how else I can assist."
            ],
            IntentType.UNKNOWN: [
                "I'm not sure I understand. Could you please rephrase?",
                "I'd like to help, but I'm not clear on what you need.",
                "Could you provide more details about what you're looking for?",
                "I want to make sure I understand correctly. Can you explain differently?"
            ]
        }