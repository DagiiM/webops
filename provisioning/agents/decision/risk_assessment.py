"""
Risk Assessment Module

Evaluates and manages risks associated with decisions and actions for the AI agent.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import uuid
import math
import random


class RiskType(Enum):
    """Types of risks that can be assessed."""
    
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    STRATEGIC = "strategic"
    COMPLIANCE = "compliance"
    REPUTATIONAL = "reputational"
    SECURITY = "security"
    TECHNICAL = "technical"
    ENVIRONMENTAL = "environmental"
    LEGAL = "legal"
    MARKET = "market"
    CREDIT = "credit"
    LIQUIDITY = "liquidity"
    SYSTEMIC = "systemic"


class RiskLevel(Enum):
    """Levels of risk severity."""
    
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCategory(Enum):
    """Categories of risk sources."""
    
    INTERNAL = "internal"
    EXTERNAL = "external"
    TECHNICAL = "technical"
    HUMAN = "human"
    ENVIRONMENTAL = "environmental"
    MARKET = "market"
    REGULATORY = "regulatory"


class RiskMitigationStrategy(Enum):
    """Strategies for mitigating risks."""
    
    AVOIDANCE = "avoidance"
    REDUCTION = "reduction"
    TRANSFER = "transfer"
    ACCEPTANCE = "acceptance"
    MONITORING = "monitoring"


@dataclass
class RiskFactor:
    """A factor that contributes to a risk."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    weight: float = 1.0  # 0.0 to 1.0, how much it contributes to risk
    value: float = 0.0  # Current value of the factor (0.0 to 1.0)
    threshold_low: float = 0.3
    threshold_high: float = 0.7
    trend: str = "stable"  # increasing, decreasing, stable
    last_updated: datetime = field(default_factory=datetime.now)
    data_source: str = ""
    confidence: float = 0.8  # Confidence in the factor value
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert risk factor to dictionary."""
        data = asdict(self)
        data['last_updated'] = self.last_updated.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RiskFactor':
        """Create risk factor from dictionary."""
        if 'last_updated' in data and isinstance(data['last_updated'], str):
            data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        return cls(**data)


@dataclass
class Risk:
    """A risk with its properties."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    risk_type: RiskType = RiskType.OPERATIONAL
    category: RiskCategory = RiskCategory.INTERNAL
    likelihood: float = 0.0  # 0.0 to 1.0
    impact: float = 0.0  # 0.0 to 1.0
    severity: float = 0.0  # 0.0 to 1.0 (likelihood * impact)
    level: RiskLevel = RiskLevel.LOW
    factors: List[RiskFactor] = field(default_factory=list)
    mitigation_strategies: List[RiskMitigationStrategy] = field(default_factory=list)
    current_mitigation_effectiveness: float = 0.0  # 0.0 to 1.0
    exposure: float = 0.0  # Current risk exposure (0.0 to 1.0)
    controls: List[str] = field(default_factory=list)
    owner: str = ""
    status: str = "active"  # active, mitigated, accepted, closed
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_assessment: Optional[datetime] = None
    next_review: Optional[datetime] = None
    probability_distribution: Optional[Dict[str, float]] = None  # Scenario probabilities
    dependencies: List[str] = field(default_factory=list) # Related risks
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert risk to dictionary."""
        data = asdict(self)
        data['risk_type'] = self.risk_type.value
        data['category'] = self.category.value
        data['level'] = self.level.value
        data['factors'] = [factor.to_dict() for factor in self.factors]
        data['mitigation_strategies'] = [strategy.value for strategy in self.mitigation_strategies]
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        data['last_assessment'] = self.last_assessment.isoformat() if self.last_assessment else None
        data['next_review'] = self.next_review.isoformat() if self.next_review else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Risk':
        """Create risk from dictionary."""
        if 'risk_type' in data and isinstance(data['risk_type'], str):
            data['risk_type'] = RiskType(data['risk_type'])
        if 'category' in data and isinstance(data['category'], str):
            data['category'] = RiskCategory(data['category'])
        if 'level' in data and isinstance(data['level'], str):
            data['level'] = RiskLevel(data['level'])
        if 'factors' in data:
            data['factors'] = [RiskFactor.from_dict(factor) for factor in data['factors']]
        if 'mitigation_strategies' in data:
            data['mitigation_strategies'] = [RiskMitigationStrategy(strategy) for strategy in data['mitigation_strategies']]
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if 'last_assessment' in data and isinstance(data['last_assessment'], str):
            data['last_assessment'] = datetime.fromisoformat(data['last_assessment'])
        if 'next_review' in data and isinstance(data['next_review'], str):
            data['next_review'] = datetime.fromisoformat(data['next_review'])
        return cls(**data)
    
    def calculate_severity(self) -> float:
        """Calculate risk severity."""
        # Apply mitigation effectiveness
        mitigated_impact = self.impact * (1.0 - self.current_mitigation_effectiveness)
        severity = self.likelihood * mitigated_impact
        return min(1.0, max(0.0, severity))
    
    def update_level(self) -> RiskLevel:
        """Update risk level based on severity."""
        severity = self.calculate_severity()
        
        if severity <= 0.1:
            level = RiskLevel.NONE
        elif severity <= 0.3:
            level = RiskLevel.LOW
        elif severity <= 0.6:
            level = RiskLevel.MEDIUM
        elif severity <= 0.8:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.CRITICAL
        
        self.level = level
        return level


@dataclass
class RiskAssessment:
    """Result of a risk assessment."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    context: str = ""  # What is being assessed
    date: datetime = field(default_factory=datetime.now)
    assessed_by: str = ""
    overall_risk_level: RiskLevel = RiskLevel.LOW
    total_risks: int = 0
    high_risks: int = 0
    critical_risks: int = 0
    risk_score: float = 0.0  # 0.0 to 1.0
    risk_trend: str = "stable"  # increasing, decreasing, stable
    recommendations: List[str] = field(default_factory=list)
    mitigation_plan: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.8  # Confidence in assessment
    duration_seconds: float = 0.0
    factors_considered: List[str] = field(default_factory=list)
    scenarios_analyzed: List[Dict[str, Any]] = field(default_factory=list)
    dependencies_identified: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert assessment to dictionary."""
        data = asdict(self)
        data['overall_risk_level'] = self.overall_risk_level.value
        data['date'] = self.date.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RiskAssessment':
        """Create assessment from dictionary."""
        if 'overall_risk_level' in data and isinstance(data['overall_risk_level'], str):
            data['overall_risk_level'] = RiskLevel(data['overall_risk_level'])
        if 'date' in data and isinstance(data['date'], str):
            data['date'] = datetime.fromisoformat(data['date'])
        return cls(**data)


@dataclass
class RiskMitigationPlan:
    """A plan for mitigating risks."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    target_risks: List[str] = field(default_factory=list)  # Risk IDs
    strategy: RiskMitigationStrategy = RiskMitigationStrategy.REDUCTION
    implementation_steps: List[Dict[str, Any]] = field(default_factory=list)
    resources_required: Dict[str, Any] = field(default_factory=dict)
    timeline: Optional[Dict[str, datetime]] = None  # start: end
    expected_effectiveness: float = 0.0  # 0.0 to 1.0
    current_effectiveness: float = 0.0  # 0.0 to 1.0
    status: str = "planned"  # planned, in_progress, completed, abandoned
    owner: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    completion_date: Optional[datetime] = None
    budget: float = 0.0
    success_metrics: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to dictionary."""
        data = asdict(self)
        data['strategy'] = self.strategy.value
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        data['completion_date'] = self.completion_date.isoformat() if self.completion_date else None
        if self.timeline:
            timeline_dict = {}
            for key, value in self.timeline.items():
                if isinstance(value, datetime):
                    timeline_dict[key] = value.isoformat()
                else:
                    timeline_dict[key] = value
            data['timeline'] = timeline_dict
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RiskMitigationPlan':
        """Create plan from dictionary."""
        if 'strategy' in data and isinstance(data['strategy'], str):
            data['strategy'] = RiskMitigationStrategy(data['strategy'])
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if 'completion_date' in data and isinstance(data['completion_date'], str):
            data['completion_date'] = datetime.fromisoformat(data['completion_date'])
        timeline = data.get('timeline')
        if timeline:
            parsed_timeline = {}
            for key, value in timeline.items():
                if isinstance(value, str):
                    parsed_timeline[key] = datetime.fromisoformat(value)
                else:
                    parsed_timeline[key] = value
            data['timeline'] = parsed_timeline
        return cls(**data)


class RiskAssessmentEngine:
    """Engine for assessing and managing risks."""
    
    def __init__(self, config):
        """Initialize the risk assessment engine."""
        self.config = config
        self.logger = logging.getLogger("risk_assessment")
        
        # Storage
        self._risks: Dict[str, Risk] = {}
        self._assessments: Dict[str, RiskAssessment] = {}
        self._mitigation_plans: Dict[str, RiskMitigationPlan] = {}
        
        # Risk models and parameters
        self._risk_models = self._initialize_risk_models()
        self._correlation_matrix = {}
        self._thresholds = self._initialize_thresholds()
        
        # Statistics
        self._total_assessments = 0
        self._total_mitigations = 0
        self._average_risk_score = 0.0
        self._risk_by_type: Dict[RiskType, List[str]] = {risk_type: [] for risk_type in RiskType}
        self._risk_by_level: Dict[RiskLevel, List[str]] = {level: [] for level in RiskLevel}
        
        # Caching
        self._assessment_cache = {}
        self._correlation_cache = {}
        
        # Configuration
        self._max_risks = 10000
        self._max_assessments = 1000
        self._max_plans = 1000
    
    async def initialize(self) -> None:
        """Initialize the risk assessment engine."""
        try:
            # Load saved data
            await self._load_saved_data()
            
            self.logger.info("Risk assessment engine initialized")
            
        except Exception as e:
            self.logger.error(f"Error initializing risk assessment engine: {e}")
            raise
    
    async def add_risk(self, risk: Risk) -> str:
        """Add a new risk to the system."""
        try:
            # Validate risk
            await self._validate_risk(risk)
            
            # Calculate initial severity and level
            risk.severity = risk.calculate_severity()
            risk.update_level()
            
            # Store risk
            self._risks[risk.id] = risk
            
            # Update indices
            await self._index_risk(risk)
            
            # Update statistics
            self._update_risk_stats(risk)
            
            self.logger.info(f"Added risk: {risk.name} ({risk.level.value})")
            return risk.id
            
        except Exception as e:
            self.logger.error(f"Error adding risk: {e}")
            raise
    
    async def assess_risks(
        self,
        context: str,
        risk_ids: Optional[List[str]] = None,
        assess_all: bool = False
    ) -> RiskAssessment:
        """Perform a comprehensive risk assessment."""
        try:
            start_time = datetime.now()
            
            # Determine which risks to assess
            if assess_all:
                risks_to_assess = list(self._risks.values())
            elif risk_ids:
                risks_to_assess = [self._risks[rid] for rid in risk_ids if rid in self._risks]
            else:
                risks_to_assess = list(self._risks.values())
            
            if not risks_to_assess:
                assessment = RiskAssessment(
                    context=context,
                    overall_risk_level=RiskLevel.NONE,
                    risk_score=0.0
                )
                return assessment
            
            # Calculate overall risk metrics
            total_risks = len(risks_to_assess)
            high_risks = sum(1 for r in risks_to_assess if r.level == RiskLevel.HIGH)
            critical_risks = sum(1 for r in risks_to_assess if r.level == RiskLevel.CRITICAL)
            
            # Calculate weighted risk score
            risk_score = sum(r.severity for r in risks_to_assess) / total_risks if total_risks > 0 else 0.0
            
            # Determine overall risk level
            if critical_risks > 0:
                overall_level = RiskLevel.CRITICAL
            elif high_risks > 0:
                overall_level = RiskLevel.HIGH
            elif risk_score > 0.6:
                overall_level = RiskLevel.MEDIUM
            elif risk_score > 0.3:
                overall_level = RiskLevel.LOW
            else:
                overall_level = RiskLevel.NONE
            
            # Identify dependencies
            dependencies = await self._identify_dependencies(risks_to_assess)
            
            # Generate recommendations
            recommendations = await self._generate_recommendations(risks_to_assess)
            
            # Create mitigation plan
            mitigation_plan = await self._generate_mitigation_plan(risks_to_assess)
            
            # Calculate risk trend
            risk_trend = await self._calculate_risk_trend(risks_to_assess)
            
            # Create assessment
            assessment = RiskAssessment(
                context=context,
                assessed_by="system",
                overall_risk_level=overall_level,
                total_risks=total_risks,
                high_risks=high_risks,
                critical_risks=critical_risks,
                risk_score=risk_score,
                risk_trend=risk_trend,
                recommendations=recommendations,
                mitigation_plan=mitigation_plan,
                dependencies_identified=dependencies
            )
            
            # Calculate duration
            end_time = datetime.now()
            assessment.duration_seconds = (end_time - start_time).total_seconds()
            
            # Store assessment
            self._assessments[assessment.id] = assessment
            self._total_assessments += 1
            
            # Update statistics
            self._update_assessment_stats(assessment)
            
            # Clean up old assessments if needed
            await self._cleanup_old_assessments()
            
            self.logger.info(f"Assessment completed: {context} (Score: {risk_score:.2f})")
            return assessment
            
        except Exception as e:
            self.logger.error(f"Error performing risk assessment: {e}")
            raise
    
    async def update_risk(
        self,
        risk_id: str,
        likelihood: Optional[float] = None,
        impact: Optional[float] = None,
        factors: Optional[List[RiskFactor]] = None
    ) -> Optional[Risk]:
        """Update an existing risk."""
        try:
            if risk_id not in self._risks:
                return None
            
            risk = self._risks[risk_id]
            
            # Update fields if provided
            if likelihood is not None:
                risk.likelihood = max(0.0, min(1.0, likelihood))
            
            if impact is not None:
                risk.impact = max(0.0, min(1.0, impact))
            
            if factors is not None:
                risk.factors = factors
            
            # Recalculate severity and level
            risk.severity = risk.calculate_severity()
            risk.update_level()
            risk.updated_at = datetime.now()
            
            # Update indices
            await self._update_risk_index(risk)
            
            # Update statistics
            self._update_risk_stats(risk)
            
            self.logger.debug(f"Updated risk: {risk_id}")
            return risk
            
        except Exception as e:
            self.logger.error(f"Error updating risk: {e}")
            return None
    
    async def create_mitigation_plan(self, plan: RiskMitigationPlan) -> str:
        """Create a risk mitigation plan."""
        try:
            # Validate plan
            await self._validate_mitigation_plan(plan)
            
            # Store plan
            self._mitigation_plans[plan.id] = plan
            self._total_mitigations += 1
            
            # Update risk mitigation effectiveness
            for risk_id in plan.target_risks:
                if risk_id in self._risks:
                    risk = self._risks[risk_id]
                    risk.current_mitigation_effectiveness = plan.current_effectiveness
                    risk.severity = risk.calculate_severity()
                    risk.update_level()
            
            self.logger.info(f"Created mitigation plan: {plan.name}")
            return plan.id
            
        except Exception as e:
            self.logger.error(f"Error creating mitigation plan: {e}")
            raise
    
    async def evaluate_decision_risk(
        self,
        decision_options: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Evaluate risks associated with different decision options."""
        try:
            results = {
                'option_risks': {},
                'recommended_option': None,
                'risk_comparison': {},
                'critical_risks': [],
                'mitigation_suggestions': {}
            }
            
            for option in decision_options:
                option_id = option.get('id', str(uuid.uuid4()))
                
                # Calculate risk for this option
                option_risk = await self._calculate_option_risk(option, context)
                results['option_risks'][option_id] = option_risk
                
                # Identify critical risks
                for risk in option_risk.get('risks', []):
                    if risk.get('level') == RiskLevel.CRITICAL.value:
                        results['critical_risks'].append({
                            'option_id': option_id,
                            'risk': risk
                        })
                
                # Generate mitigation suggestions
                results['mitigation_suggestions'][option_id] = await self._generate_mitigation_suggestions(
                    option_risk.get('risks', [])
                )
            
            # Compare risks across options
            results['risk_comparison'] = await self._compare_option_risks(
                results['option_risks']
            )
            
            # Recommend best option based on risk
            results['recommended_option'] = await self._recommend_lowest_risk_option(
                results['option_risks']
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error evaluating decision risk: {e}")
            return {'error': str(e)}
    
    async def get_risk_exposure(self, risk_ids: List[str]) -> Dict[str, float]:
        """Get current risk exposure for specified risks."""
        exposure = {}
        
        for risk_id in risk_ids:
            if risk_id in self._risks:
                risk = self._risks[risk_id]
                # Exposure is severity adjusted for mitigation
                exposure[risk_id] = risk.severity * (1.0 - risk.current_mitigation_effectiveness)
        
        return exposure
    
    async def simulate_risk_scenarios(
        self,
        risk_ids: List[str],
        scenarios: int = 1000
    ) -> Dict[str, Any]:
        """Simulate risk scenarios using Monte Carlo methods."""
        try:
            results = {
                'scenarios': [],
                'risk_correlation': {},
                'worst_case': {},
                'best_case': {},
                'expected_value': {},
                'confidence_intervals': {}
            }
            
            # Get risks to simulate
            risks = [self._risks[rid] for rid in risk_ids if rid in self._risks]
            
            # Run Monte Carlo simulation
            scenario_results = []
            for _ in range(scenarios):
                scenario = {}
                total_exposure = 0.0
                
                for risk in risks:
                    # Simulate risk occurrence based on likelihood
                    if random.random() < risk.likelihood:
                        # Apply impact
                        impact = risk.impact * (1.0 - risk.current_mitigation_effectiveness)
                        scenario[risk.id] = {
                            'occurred': True,
                            'impact': impact,
                            'severity': risk.severity
                        }
                        total_exposure += impact
                    else:
                        scenario[risk.id] = {
                            'occurred': False,
                            'impact': 0.0,
                            'severity': risk.severity
                        }
                
                scenario['total_exposure'] = total_exposure
                scenario_results.append(scenario)
            
            # Analyze results
            total_exposures = [s['total_exposure'] for s in scenario_results]
            results['expected_value']['total_exposure'] = sum(total_exposures) / len(total_exposures)
            results['worst_case']['total_exposure'] = max(total_exposures)
            results['best_case']['total_exposure'] = min(total_exposures)
            
            # Calculate confidence intervals (95%)
            sorted_exposures = sorted(total_exposures)
            n = len(sorted_exposures)
            results['confidence_intervals']['total_exposure'] = {
                'lower_95': sorted_exposures[int(0.025 * n)],
                'upper_95': sorted_exposures[int(0.975 * n)]
            }
            
            results['scenarios'] = scenario_results
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error simulating risk scenarios: {e}")
            return {'error': str(e)}
    
    async def get_risk_dashboard(self) -> Dict[str, Any]:
        """Get a dashboard view of risk status."""
        try:
            dashboard = {
                'summary': {
                    'total_risks': len(self._risks),
                    'total_assessments': self._total_assessments,
                    'total_mitigations': self._total_mitigations,
                    'average_risk_score': self._average_risk_score,
                    'risks_by_level': {
                        level.value: len(risk_list)
                        for level, risk_list in self._risk_by_level.items()
                    },
                    'risks_by_type': {
                        risk_type.value: len(risk_list)
                        for risk_type, risk_list in self._risk_by_type.items()
                    }
                },
                'trends': await self._calculate_risk_trends(),
                'top_risks': await self._get_top_risks(10),
                'mitigation_status': await self._get_mitigation_status(),
                'recent_assessments': await self._get_recent_assessments(5),
                'risk_map': await self._generate_risk_map()
            }
            
            return dashboard
            
        except Exception as e:
            self.logger.error(f"Error generating risk dashboard: {e}")
            return {'error': str(e)}
    
    async def get_risk_statistics(self) -> Dict[str, Any]:
        """Get risk assessment statistics."""
        try:
            stats = {
                'total_risks': len(self._risks),
                'total_assessments': self._total_assessments,
                'total_mitigations': self._total_mitigations,
                'average_risk_score': self._average_risk_score,
                'risks_by_level': {
                    level.value: len(risk_list)
                    for level, risk_list in self._risk_by_level.items()
                },
                'risks_by_category': {
                    category.value: len([r for r in self._risks.values() if r.category == category])
                    for category in RiskCategory
                },
                'risks_by_type': {
                    risk_type.value: len(risk_list)
                    for risk_type, risk_list in self._risk_by_type.items()
                },
                'mitigation_effectiveness': await self._calculate_mitigation_effectiveness(),
                'risk_trends': await self._calculate_risk_trends(),
                'most_common_factors': await self._get_most_common_risk_factors(),
                'recent_activity': {
                    'last_assessment': max(
                        (a.date for a in self._assessments.values()), 
                        default=None
                    ).isoformat() if self._assessments else None,
                    'last_mitigation': max(
                        (p.created_at for p in self._mitigation_plans.values()), 
                        default=None
                    ).isoformat() if self._mitigation_plans else None
                }
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting risk statistics: {e}")
            return {}
    
    async def _validate_risk(self, risk: Risk) -> None:
        """Validate risk data."""
        if not risk.name:
            raise ValueError("Risk name is required")
        
        if not (0.0 <= risk.likelihood <= 1.0):
            raise ValueError("Risk likelihood must be between 0.0 and 1.0")
        
        if not (0.0 <= risk.impact <= 1.0):
            raise ValueError("Risk impact must be between 0.0 and 1.0")
        
        if risk.current_mitigation_effectiveness < 0.0 or risk.current_mitigation_effectiveness > 1.0:
            raise ValueError("Mitigation effectiveness must be between 0.0 and 1.0")
    
    async def _validate_mitigation_plan(self, plan: RiskMitigationPlan) -> None:
        """Validate mitigation plan."""
        if not plan.name:
            raise ValueError("Plan name is required")
        
        if not plan.target_risks:
            raise ValueError("Plan must target at least one risk")
        
        if not (0.0 <= plan.expected_effectiveness <= 1.0):
            raise ValueError("Expected effectiveness must be between 0.0 and 1.0")
    
    async def _index_risk(self, risk: Risk) -> None:
        """Index risk for efficient retrieval."""
        # Add to type index
        if risk.id not in self._risk_by_type[risk.risk_type]:
            self._risk_by_type[risk.risk_type].append(risk.id)
        
        # Add to level index
        if risk.id not in self._risk_by_level[risk.level]:
            self._risk_by_level[risk.level].append(risk.id)
    
    async def _update_risk_index(self, risk: Risk) -> None:
        """Update risk indices."""
        # Remove from old indices
        for risk_type, risk_list in self._risk_by_type.items():
            if risk.id in risk_list and risk_type != risk.risk_type:
                risk_list.remove(risk.id)
        
        for level, risk_list in self._risk_by_level.items():
            if risk.id in risk_list and level != risk.level:
                risk_list.remove(risk.id)
        
        # Add to new indices
        if risk.id not in self._risk_by_type[risk.risk_type]:
            self._risk_by_type[risk.risk_type].append(risk.id)
        
        if risk.id not in self._risk_by_level[risk.level]:
            self._risk_by_level[risk.level].append(risk.id)
    
    async def _update_risk_stats(self, risk: Risk) -> None:
        """Update risk statistics."""
        # Update average risk score using running average
        if self._total_assessments == 0:
            self._average_risk_score = risk.severity
        else:
            # Weighted average considering all risks
            all_severities = [r.severity for r in self._risks.values()]
            if all_severities:
                self._average_risk_score = sum(all_severities) / len(all_severities)
    
    async def _update_assessment_stats(self, assessment: RiskAssessment) -> None:
        """Update assessment statistics."""
        # Update average risk score
        if self._total_assessments == 1:
            self._average_risk_score = assessment.risk_score
        else:
            # Running average
            alpha = 0.1  # Smoothing factor
            self._average_risk_score = (
                alpha * assessment.risk_score +
                (1 - alpha) * self._average_risk_score
            )
    
    async def _identify_dependencies(self, risks: List[Risk]) -> List[str]:
        """Identify dependencies between risks."""
        dependencies = []
        
        # Simple dependency detection based on category and type
        for i, risk1 in enumerate(risks):
            for j, risk2 in enumerate(risks):
                if i != j:
                    # Check if risks are related
                    if (risk1.category == risk2.category or 
                        risk1.risk_type == risk2.risk_type):
                        dependency = f"{risk1.id} -> {risk2.id}"
                        if dependency not in dependencies:
                            dependencies.append(dependency)
        
        return dependencies
    
    async def _generate_recommendations(self, risks: List[Risk]) -> List[str]:
        """Generate recommendations based on identified risks."""
        recommendations = []
        
        # High and critical risks need immediate attention
        high_critical_risks = [r for r in risks if r.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]]
        
        if high_critical_risks:
            recommendations.append("Prioritize mitigation of high and critical risks immediately")
        
        # Risks with low mitigation effectiveness
        low_mitigation_risks = [r for r in risks if r.current_mitigation_effectiveness < 0.3]
        if low_mitigation_risks:
            recommendations.append("Review and improve mitigation strategies for poorly mitigated risks")
        
        # Risks with increasing trend
        increasing_risks = [r for r in risks if r.factors and any(f.trend == "increasing" for f in r.factors)]
        if increasing_risks:
            recommendations.append("Monitor and address risks with increasing trend factors")
        
        return recommendations
    
    async def _generate_mitigation_plan(self, risks: List[Risk]) -> List[Dict[str, Any]]:
        """Generate mitigation plan for risks."""
        plan = []
        
        for risk in risks:
            if risk.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                strategy = RiskMitigationStrategy.REDUCTION
                if risk.category == RiskCategory.EXTERNAL:
                    strategy = RiskMitigationStrategy.MONITORING
                elif risk.category == RiskCategory.HUMAN:
                    strategy = RiskMitigationStrategy.REDUCTION
                
                plan.append({
                    'risk_id': risk.id,
                    'risk_name': risk.name,
                    'recommended_strategy': strategy.value,
                    'priority': risk.level.value,
                    'estimated_effectiveness': 0.7 if risk.level == RiskLevel.HIGH else 0.9
                })
        
        return plan
    
    async def _calculate_risk_trend(self, risks: List[Risk]) -> str:
        """Calculate overall risk trend."""
        if not risks:
            return "stable"
        
        increasing_factors = sum(
            1 for risk in risks
            for factor in risk.factors
            if factor.trend == "increasing"
        )
        
        decreasing_factors = sum(
            1 for risk in risks
            for factor in risk.factors
            if factor.trend == "decreasing"
        )
        
        if increasing_factors > decreasing_factors * 1.5:
            return "increasing"
        elif decreasing_factors > increasing_factors * 1.5:
            return "decreasing"
        else:
            return "stable"
    
    async def _calculate_option_risk(
        self,
        option: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate risk for a specific option."""
        # This is a simplified risk calculation
        # In a real implementation, this would be more sophisticated
        
        base_risk = option.get('base_risk', 0.3)  # Default medium risk
        complexity_factor = option.get('complexity', 0.5)
        novelty_factor = option.get('novelty', 0.3)
        
        # Calculate risk multipliers based on option properties
        risk_multipliers = {
            'complexity': 1.0 + (complexity_factor * 0.5),
            'novelty': 1.0 + (novelty_factor * 0.3),
            'resource_intensive': option.get('resource_intensive', False) * 0.2,
            'time_sensitive': option.get('time_sensitive', False) * 0.15
        }
        
        # Apply multipliers
        total_risk = base_risk
        for multiplier in risk_multipliers.values():
            total_risk *= (1.0 + multiplier)
        
        # Cap at 1.0
        total_risk = min(1.0, total_risk)
        
        # Determine risk level
        if total_risk <= 0.2:
            level = RiskLevel.LOW
        elif total_risk <= 0.4:
            level = RiskLevel.MEDIUM
        elif total_risk <= 0.7:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.CRITICAL
        
        return {
            'option_id': option.get('id'),
            'risk_score': total_risk,
            'level': level.value,
            'factors': risk_multipliers,
            'risks': [
                {
                    'name': 'General Risk',
                    'score': total_risk,
                    'level': level.value,
                    'description': f"Overall risk assessment for option {option.get('id')}"
                }
            ]
        }
    
    async def _generate_mitigation_suggestions(self, risks: List[Dict[str, Any]]) -> List[str]:
        """Generate mitigation suggestions for risks."""
        suggestions = []
        
        for risk in risks:
            if risk['level'] == RiskLevel.CRITICAL.value:
                suggestions.append(f"Implement immediate mitigation for critical risk: {risk['name']}")
            elif risk['level'] == RiskLevel.HIGH.value:
                suggestions.append(f"Develop detailed mitigation plan for high risk: {risk['name']}")
            elif risk['score'] > 0.5:
                suggestions.append(f"Consider mitigation options for risk: {risk['name']}")
        
        return suggestions
    
    async def _compare_option_risks(self, option_risks: Dict[str, Any]) -> Dict[str, Any]:
        """Compare risks across different options."""
        comparison = {
            'lowest_risk_option': None,
            'highest_risk_option': None,
            'risk_difference': 0.0,
            'relative_safety': {}
        }
        
        if not option_risks:
            return comparison
        
        # Calculate risk scores for each option
        risk_scores = {}
        for option_id, risk_data in option_risks.items():
            risk_scores[option_id] = risk_data.get('risk_score', 0.0)
        
        if not risk_scores:
            return comparison
        
        # Find lowest and highest risk options
        lowest_risk_option = min(risk_scores, key=risk_scores.get)
        highest_risk_option = max(risk_scores, key=risk_scores.get)
        
        comparison['lowest_risk_option'] = lowest_risk_option
        comparison['highest_risk_option'] = highest_risk_option
        comparison['risk_difference'] = risk_scores[highest_risk_option] - risk_scores[lowest_risk_option]
        
        # Calculate relative safety
        for option_id, score in risk_scores.items():
            comparison['relative_safety'][option_id] = 1.0 - score
        
        return comparison
    
    async def _recommend_lowest_risk_option(self, option_risks: Dict[str, Any]) -> Optional[str]:
        """Recommend the lowest risk option."""
        if not option_risks:
            return None
        
        # Find option with lowest risk score
        lowest_risk_option = None
        lowest_score = float('inf')
        
        for option_id, risk_data in option_risks.items():
            score = risk_data.get('risk_score', 0.0)
            if score < lowest_score:
                lowest_score = score
                lowest_risk_option = option_id
        
        return lowest_risk_option
    
    async def _calculate_mitigation_effectiveness(self) -> float:
        """Calculate overall mitigation effectiveness."""
        if not self._risks:
            return 0.0
        
        effectiveness_values = [
            risk.current_mitigation_effectiveness 
            for risk in self._risks.values()
        ]
        
        if not effectiveness_values:
            return 0.0
        
        return sum(effectiveness_values) / len(effectiveness_values)
    
    async def _calculate_risk_trends(self) -> Dict[str, Any]:
        """Calculate risk trends."""
        trends = {
            'overall_trend': 'stable',
            'by_level': {},
            'by_type': {}
        }
        
        # Calculate trend by level
        for level, risk_list in self._risk_by_level.items():
            if risk_list:
                level_risks = [self._risks[rid] for rid in risk_list]
                trends['by_level'][level.value] = await self._calculate_level_trend(level_risks)
        
        # Calculate trend by type
        for risk_type, risk_list in self._risk_by_type.items():
            if risk_list:
                type_risks = [self._risks[rid] for rid in risk_list]
                trends['by_type'][risk_type.value] = await self._calculate_type_trend(type_risks)
        
        return trends
    
    async def _calculate_level_trend(self, risks: List[Risk]) -> str:
        """Calculate trend for risks of a specific level."""
        if not risks:
            return "stable"
        
        # Look at factors' trends
        increasing_factors = sum(1 for r in risks for f in r.factors if f.trend == "increasing")
        decreasing_factors = sum(1 for r in risks for f in r.factors if f.trend == "decreasing")
        
        if increasing_factors > decreasing_factors * 1.5:
            return "increasing"
        elif decreasing_factors > increasing_factors * 1.5:
            return "decreasing"
        else:
            return "stable"
    
    async def _calculate_type_trend(self, risks: List[Risk]) -> str:
        """Calculate trend for risks of a specific type."""
        if not risks:
            return "stable"
        
        # Look at factors' trends
        increasing_factors = sum(1 for r in risks for f in r.factors if f.trend == "increasing")
        decreasing_factors = sum(1 for r in risks for f in r.factors if f.trend == "decreasing")
        
        if increasing_factors > decreasing_factors * 1.5:
            return "increasing"
        elif decreasing_factors > increasing_factors * 1.5:
            return "decreasing"
        else:
            return "stable"
    
    async def _get_top_risks(self, count: int) -> List[Dict[str, Any]]:
        """Get top risks by severity."""
        sorted_risks = sorted(
            self._risks.values(),
            key=lambda r: r.severity,
            reverse=True
        )
        
        top_risks = []
        for risk in sorted_risks[:count]:
            top_risks.append({
                'id': risk.id,
                'name': risk.name,
                'severity': risk.severity,
                'level': risk.level.value,
                'type': risk.risk_type.value,
                'category': risk.category.value,
                'likelihood': risk.likelihood,
                'impact': risk.impact
            })
        
        return top_risks
    
    async def _get_mitigation_status(self) -> Dict[str, Any]:
        """Get mitigation plan status."""
        status = {
            'total_plans': len(self._mitigation_plans),
            'by_status': {},
            'effectiveness_stats': {}
        }
        
        # Count by status
        for plan in self._mitigation_plans.values():
            status_value = plan.status
            if status_value not in status['by_status']:
                status['by_status'][status_value] = 0
            status['by_status'][status_value] += 1
        
        # Calculate effectiveness statistics
        effectiveness_values = [plan.current_effectiveness for plan in self._mitigation_plans.values()]
        if effectiveness_values:
            status['effectiveness_stats'] = {
                'average': sum(effectiveness_values) / len(effectiveness_values),
                'min': min(effectiveness_values),
                'max': max(effectiveness_values)
            }
        
        return status
    
    async def _get_recent_assessments(self, count: int) -> List[Dict[str, Any]]:
        """Get recent risk assessments."""
        sorted_assessments = sorted(
            self._assessments.values(),
            key=lambda a: a.date,
            reverse=True
        )
        
        recent_assessments = []
        for assessment in sorted_assessments[:count]:
            recent_assessments.append({
                'id': assessment.id,
                'context': assessment.context,
                'date': assessment.date.isoformat(),
                'overall_risk_level': assessment.overall_risk_level.value,
                'risk_score': assessment.risk_score,
                'total_risks': assessment.total_risks
            })
        
        return recent_assessments
    
    async def _generate_risk_map(self) -> List[Dict[str, Any]]:
        """Generate a risk map (likelihood vs impact)."""
        risk_map = []
        
        for risk in self._risks.values():
            risk_map.append({
                'id': risk.id,
                'name': risk.name,
                'likelihood': risk.likelihood,
                'impact': risk.impact,
                'severity': risk.severity,
                'level': risk.level.value,
                'type': risk.risk_type.value
            })
        
        return risk_map
    
    async def _get_most_common_risk_factors(self) -> List[Dict[str, Any]]:
        """Get most common risk factors."""
        factor_counts = {}
        
        for risk in self._risks.values():
            for factor in risk.factors:
                if factor.name in factor_counts:
                    factor_counts[factor.name] += 1
                else:
                    factor_counts[factor.name] = 1
        
        # Sort by count
        sorted_factors = sorted(
            factor_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [{'name': name, 'count': count} for name, count in sorted_factors[:10]]
    
    async def _cleanup_old_assessments(self) -> None:
        """Clean up old assessments to manage memory."""
        if len(self._assessments) > self._max_assessments:
            # Sort by date and keep only the most recent ones
            sorted_assessments = sorted(
                self._assessments.items(),
                key=lambda x: x[1].date,
                reverse=True
            )
            
            # Keep only the most recent ones
            recent_assessments = dict(sorted_assessments[:self._max_assessments - 100])
            self._assessments = recent_assessments
    
    async def _load_saved_data(self) -> None:
        """Load saved risks, assessments, and mitigation plans."""
        # In a real implementation, this would load from persistent storage
        # For now, just initialize empty collections
        pass
    
    def _initialize_risk_models(self) -> Dict[str, Any]:
        """Initialize risk models and parameters."""
        return {
            'financial': {
                'base_probability': 0.1,
                'impact_multiplier': 2.0,
                'mitigation_factor': 0.7
            },
            'operational': {
                'base_probability': 0.3,
                'impact_multiplier': 1.5,
                'mitigation_factor': 0.6
            },
            'strategic': {
                'base_probability': 0.2,
                'impact_multiplier': 3.0,
                'mitigation_factor': 0.5
            }
        }
    
    def _initialize_thresholds(self) -> Dict[str, float]:
        """Initialize risk thresholds."""
        return {
            'low_to_medium': 0.3,
            'medium_to_high': 0.6,
            'high_to_critical': 0.8
        }