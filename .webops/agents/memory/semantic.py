"""
Semantic Memory Module

Stores and retrieves factual knowledge and concepts for the AI agent.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import uuid
import re


class FactType(Enum):
    """Types of facts stored in semantic memory."""
    
    PROCEDURE = "procedure"
    CONCEPT = "concept"
    RULE = "rule"
    DEFINITION = "definition"
    RELATIONSHIP = "relationship"
    METADATA = "metadata"
    CONFIGURATION = "configuration"
    GENERAL = "general"


class FactStatus(Enum):
    """Status of facts in semantic memory."""
    
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    CONFLICTING = "conflicting"
    PENDING = "pending"
    VERIFIED = "verified"


@dataclass
class Fact:
    """A factual piece of knowledge stored in semantic memory."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    fact_type: FactType = FactType.GENERAL
    category: str = "general"
    confidence: float = 0.5
    source: str = "agent"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    status: FactStatus = FactStatus.ACTIVE
    verification_count: int = 0
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    related_facts: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert fact to dictionary."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        data['fact_type'] = self.fact_type.value
        data['status'] = self.status.value
        data['last_accessed'] = self.last_accessed.isoformat() if self.last_accessed else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Fact':
        """Create fact from dictionary."""
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if 'fact_type' in data and isinstance(data['fact_type'], str):
            data['fact_type'] = FactType(data['fact_type'])
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = FactStatus(data['status'])
        if 'last_accessed' in data and isinstance(data['last_accessed'], str):
            data['last_accessed'] = datetime.fromisoformat(data['last_accessed'])
        return cls(**data)
    
    def calculate_relevance(self, query: str) -> float:
        """Calculate relevance of this fact to a query."""
        query_lower = query.lower()
        content_lower = self.content.lower()
        
        # Exact match gets highest score
        if query_lower == content_lower:
            return 1.0
        
        # Check for query in content
        if query_lower in content_lower:
            return 0.8
        
        # Check for word overlap
        query_words = set(query_lower.split())
        content_words = set(content_lower.split())
        
        if query_words and content_words:
            overlap = len(query_words & content_words)
            return overlap / len(query_words)
        
        # Check tag matches
        tag_matches = sum(1 for tag in self.tags if query_lower in tag.lower())
        if tag_matches > 0:
            return 0.3 * (tag_matches / len(self.tags)) if self.tags else 0.3
        
        return 0.0


@dataclass
class Knowledge:
    """A knowledge structure containing related facts."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    facts: List[str] = field(default_factory=list)
    relationships: Dict[str, List[str]] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert knowledge to dictionary."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data


class SemanticMemory:
    """Stores and retrieves factual knowledge."""
    
    def __init__(self, config):
        """Initialize semantic memory."""
        self.config = config
        self.logger = logging.getLogger("semantic_memory")
        
        # Storage
        self._facts: Dict[str, Fact] = {}
        self._knowledge: Dict[str, Knowledge] = {}
        
        # Indices
        self._content_index: Dict[str, List[str]] = {}
        self._tag_index: Dict[str, List[str]] = {}
        self._category_index: Dict[str, List[str]] = {}
        self._type_index: Dict[FactType, List[str]] = {
            fact_type: [] for fact_type in FactType
        }
        
        # Statistics
        self._total_facts = 0
        self._total_knowledge = 0
        self._last_cleanup = datetime.now()
    
    async def store_fact(self, fact: Fact) -> str:
        """Store a factual piece of knowledge."""
        try:
            # Check for duplicates
            duplicate_id = await self._find_duplicate(fact)
            if duplicate_id:
                # Update existing fact
                await self._update_fact(duplicate_id, fact)
                return duplicate_id
            
            # Store new fact
            self._facts[fact.id] = fact
            
            # Update indices
            await self._index_fact(fact)
            
            # Update statistics
            self._total_facts += 1
            
            # Check if cleanup is needed
            await self._check_cleanup()
            
            self.logger.debug(f"Stored fact: {fact.id}")
            return fact.id
            
        except Exception as e:
            self.logger.error(f"Error storing fact: {e}")
            raise
    
    async def get_fact(self, fact_id: str) -> Optional[Fact]:
        """Get a fact by ID."""
        if fact_id in self._facts:
            # Update access statistics
            fact = self._facts[fact_id]
            fact.last_accessed = datetime.now()
            fact.access_count += 1
            return fact
        return None
    
    async def query_facts(
        self,
        query: str,
        limit: int = 10,
        category: Optional[str] = None,
        fact_type: Optional[FactType] = None,
        min_confidence: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Query semantic memory for facts."""
        try:
            results = []
            
            # Filter facts
            filtered_facts = []
            for fact in self._facts.values():
                if fact.status != FactStatus.ACTIVE:
                    continue
                if category and fact.category != category:
                    continue
                if fact_type and fact.fact_type != fact_type:
                    continue
                if fact.confidence < min_confidence:
                    continue
                filtered_facts.append(fact)
            
            # Calculate relevance and sort
            fact_relevance = []
            for fact in filtered_facts:
                relevance = fact.calculate_relevance(query)
                if relevance > 0:
                    fact_relevance.append((relevance, fact))
            
            fact_relevance.sort(key=lambda x: x[0], reverse=True)
            
            # Convert to results
            for relevance, fact in fact_relevance[:limit]:
                results.append({
                    'fact_id': fact.id,
                    'content': fact.content,
                    'fact_type': fact.fact_type.value,
                    'category': fact.category,
                    'confidence': fact.confidence,
                    'relevance': relevance,
                    'source': fact.source,
                    'tags': fact.tags,
                    'created_at': fact.created_at.isoformat(),
                    'access_count': fact.access_count
                })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error querying facts: {e}")
            return []
    
    async def update_fact(self, fact_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing fact."""
        try:
            if fact_id not in self._facts:
                return False
            
            fact = self._facts[fact_id]
            
            # Remove old indices
            await self._unindex_fact(fact)
            
            # Update fields
            for key, value in updates.items():
                if hasattr(fact, key):
                    setattr(fact, key, value)
            
            fact.updated_at = datetime.now()
            
            # Re-index
            await self._index_fact(fact)
            
            self.logger.debug(f"Updated fact: {fact_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating fact: {e}")
            return False
    
    async def delete_fact(self, fact_id: str) -> bool:
        """Delete a fact."""
        try:
            if fact_id not in self._facts:
                return False
            
            fact = self._facts[fact_id]
            
            # Remove from indices
            await self._unindex_fact(fact)
            
            # Remove from storage
            del self._facts[fact_id]
            self._total_facts -= 1
            
            self.logger.debug(f"Deleted fact: {fact_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting fact: {e}")
            return False
    
    async def create_knowledge(
        self,
        name: str,
        description: str,
        fact_ids: List[str]
    ) -> str:
        """Create a knowledge structure from related facts."""
        try:
            # Validate facts exist
            valid_fact_ids = [
                fid for fid in fact_ids
                if fid in self._facts
            ]
            
            if not valid_fact_ids:
                raise ValueError("No valid facts provided")
            
            # Create knowledge
            knowledge = Knowledge(
                name=name,
                description=description,
                facts=valid_fact_ids
            )
            
            # Store knowledge
            self._knowledge[knowledge.id] = knowledge
            self._total_knowledge += 1
            
            # Update fact relationships
            for fact_id in valid_fact_ids:
                fact = self._facts[fact_id]
                if knowledge.id not in fact.related_facts:
                    fact.related_facts.append(knowledge.id)
            
            self.logger.info(f"Created knowledge: {knowledge.id}")
            return knowledge.id
            
        except Exception as e:
            self.logger.error(f"Error creating knowledge: {e}")
            raise
    
    async def get_knowledge(self, knowledge_id: str) -> Optional[Knowledge]:
        """Get knowledge by ID."""
        return self._knowledge.get(knowledge_id)
    
    async def search_knowledge(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for knowledge structures."""
        try:
            results = []
            query_lower = query.lower()
            
            for knowledge in self._knowledge.values():
                relevance = 0.0
                
                # Check name match
                if query_lower in knowledge.name.lower():
                    relevance += 0.5
                
                # Check description match
                if query_lower in knowledge.description.lower():
                    relevance += 0.3
                
                # Check fact content matches
                fact_matches = 0
                for fact_id in knowledge.facts:
                    if fact_id in self._facts:
                        fact = self._facts[fact_id]
                        if query_lower in fact.content.lower():
                            fact_matches += 1
                
                if fact_matches > 0:
                    relevance += 0.2 * (fact_matches / len(knowledge.facts))
                
                if relevance > 0:
                    results.append({
                        'knowledge_id': knowledge.id,
                        'name': knowledge.name,
                        'description': knowledge.description,
                        'relevance': relevance,
                        'fact_count': len(knowledge.facts),
                        'created_at': knowledge.created_at.isoformat()
                    })
            
            # Sort by relevance
            results.sort(key=lambda x: x['relevance'], reverse=True)
            return results[:limit]
            
        except Exception as e:
            self.logger.error(f"Error searching knowledge: {e}")
            return []
    
    async def consolidate_knowledge(self) -> None:
        """Consolidate and optimize knowledge storage."""
        try:
            self.logger.info("Starting knowledge consolidation")
            
            # Find related facts
            await self._find_related_facts()
            
            # Remove outdated facts
            await self._remove_outdated_facts()
            
            # Optimize indices
            await self._optimize_indices()
            
            self.logger.info("Knowledge consolidation completed")
            
        except Exception as e:
            self.logger.error(f"Error consolidating knowledge: {e}")
    
    async def cleanup_old_facts(self, cutoff_date: datetime) -> int:
        """Clean up old facts based on retention policy."""
        try:
            removed_count = 0
            
            # Find old, low-confidence facts
            old_fact_ids = [
                fid for fid, fact in self._facts.items()
                if (fact.created_at < cutoff_date and 
                    fact.confidence < 0.5 and 
                    fact.access_count < 5)
            ]
            
            # Remove old facts
            for fact_id in old_fact_ids:
                if await self.delete_fact(fact_id):
                    removed_count += 1
            
            self.logger.info(f"Cleaned up {removed_count} old facts")
            return removed_count
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old facts: {e}")
            return 0
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get semantic memory statistics."""
        try:
            stats = {
                'total_facts': len(self._facts),
                'total_knowledge': len(self._knowledge),
                'facts_by_type': {
                    fact_type.value: len(ids)
                    for fact_type, ids in self._type_index.items()
                },
                'facts_by_category': {},
                'total_categories': len(self._category_index),
                'total_tags': len(self._tag_index),
                'average_confidence': 0.0,
                'last_cleanup': self._last_cleanup.isoformat()
            }
            
            # Calculate category distribution
            for category, fact_ids in self._category_index.items():
                stats['facts_by_category'][category] = len(fact_ids)
            
            # Calculate average confidence
            if self._facts:
                stats['average_confidence'] = sum(
                    fact.confidence for fact in self._facts.values()
                ) / len(self._facts)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting memory stats: {e}")
            return {}
    
    async def _find_duplicate(self, fact: Fact) -> Optional[str]:
        """Find duplicate fact."""
        for existing_id, existing_fact in self._facts.items():
            if (existing_fact.content.lower() == fact.content.lower() and
                existing_fact.fact_type == fact.fact_type):
                return existing_id
        return None
    
    async def _update_fact(self, fact_id: str, new_fact: Fact) -> None:
        """Update existing fact with new information."""
        existing_fact = self._facts[fact_id]
        
        # Merge information
        existing_fact.confidence = max(existing_fact.confidence, new_fact.confidence)
        existing_fact.tags = list(set(existing_fact.tags + new_fact.tags))
        existing_fact.metadata.update(new_fact.metadata)
        existing_fact.updated_at = datetime.now()
        existing_fact.verification_count += 1
    
    async def _index_fact(self, fact: Fact) -> None:
        """Index a fact for efficient retrieval."""
        # Content index (words)
        words = re.findall(r'\b\w+\b', fact.content.lower())
        for word in words:
            if word not in self._content_index:
                self._content_index[word] = []
            if fact.id not in self._content_index[word]:
                self._content_index[word].append(fact.id)
        
        # Tag index
        for tag in fact.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            if fact.id not in self._tag_index[tag]:
                self._tag_index[tag].append(fact.id)
        
        # Category index
        if fact.category not in self._category_index:
            self._category_index[fact.category] = []
        if fact.id not in self._category_index[fact.category]:
            self._category_index[fact.category].append(fact.id)
        
        # Type index
        if fact.id not in self._type_index[fact.fact_type]:
            self._type_index[fact.fact_type].append(fact.id)
    
    async def _unindex_fact(self, fact: Fact) -> None:
        """Remove a fact from indices."""
        # Content index
        words = re.findall(r'\b\w+\b', fact.content.lower())
        for word in words:
            if word in self._content_index and fact.id in self._content_index[word]:
                self._content_index[word].remove(fact.id)
                if not self._content_index[word]:
                    del self._content_index[word]
        
        # Tag index
        for tag in fact.tags:
            if tag in self._tag_index and fact.id in self._tag_index[tag]:
                self._tag_index[tag].remove(fact.id)
                if not self._tag_index[tag]:
                    del self._tag_index[tag]
        
        # Category index
        if (fact.category in self._category_index and 
            fact.id in self._category_index[fact.category]):
            self._category_index[fact.category].remove(fact.id)
            if not self._category_index[fact.category]:
                del self._category_index[fact.category]
        
        # Type index
        if fact.id in self._type_index[fact.fact_type]:
            self._type_index[fact.fact_type].remove(fact.id)
    
    async def _check_cleanup(self) -> None:
        """Check if cleanup is needed."""
        # Cleanup every hour or if we have too many facts
        if (datetime.now() - self._last_cleanup > timedelta(hours=1) or
            len(self._facts) > 10000):
            await self.consolidate_knowledge()
            self._last_cleanup = datetime.now()
    
    async def _find_related_facts(self) -> None:
        """Find and link related facts."""
        # Clear existing relationships
        for fact in self._facts.values():
            fact.related_facts.clear()
        
        # Find relationships based on shared tags and content
        for fact_id, fact in self._facts.items():
            related = []
            
            # Find facts with shared tags
            for tag in fact.tags:
                if tag in self._tag_index:
                    for related_id in self._tag_index[tag]:
                        if related_id != fact_id and related_id not in related:
                            related.append(related_id)
            
            # Limit to top 5 related facts
            fact.related_facts = related[:5]
    
    async def _remove_outdated_facts(self) -> None:
        """Remove outdated or conflicting facts."""
        to_remove = []
        
        for fact_id, fact in self._facts.items():
            # Mark very old, unused facts as deprecated
            if (fact.created_at < datetime.now() - timedelta(days=90) and
                fact.access_count == 0 and
                fact.confidence < 0.3):
                fact.status = FactStatus.DEPRECICATED
            
            # Mark conflicting facts
            for other_id, other_fact in self._facts.items():
                if (fact_id != other_id and
                    fact.content.lower() == other_fact.content.lower() and
                    fact.fact_type == other_fact.fact_type and
                    fact.confidence != other_fact.confidence):
                    # Keep the one with higher confidence
                    if fact.confidence < other_fact.confidence:
                        fact.status = FactStatus.CONFLICTING
        
        # Actually remove deprecated facts
        for fact_id in list(self._facts.keys()):
            if self._facts[fact_id].status == FactStatus.DEPRECATED:
                to_remove.append(fact_id)
        
        for fact_id in to_remove:
            await self.delete_fact(fact_id)
    
    async def _optimize_indices(self) -> None:
        """Optimize indices for better performance."""
        # Remove stale entries
        all_fact_ids = set(self._facts.keys())
        
        # Clean content index
        for word in list(self._content_index.keys()):
            self._content_index[word] = [
                fid for fid in self._content_index[word]
                if fid in all_fact_ids
            ]
            if not self._content_index[word]:
                del self._content_index[word]
        
        # Clean other indices
        for index_dict in [self._tag_index, self._category_index]:
            for key in list(index_dict.keys()):
                index_dict[key] = [
                    fid for fid in index_dict[key]
                    if fid in all_fact_ids
                ]
                if not index_dict[key]:
                    del index_dict[key]