"""
Setup script for AI Agent System

Comprehensive setup configuration for the WebOps AI Agent System.
"""

import os
from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
README_PATH = Path(__file__).parent.parent / "README.md"
LONG_DESCRIPTION = ""
if README_PATH.exists():
    with open(README_PATH, "r", encoding="utf-8") as f:
        LONG_DESCRIPTION = f.read()

# Read requirements
REQUIREMENTS_PATH = Path(__file__).parent / "requirements.txt"
REQUIREMENTS = []
if REQUIREMENTS_PATH.exists():
    with open(REQUIREMENTS_PATH, "r", encoding="utf-8") as f:
        REQUIREMENTS = [
            line.strip()
            for line in f.readlines()
            if line.strip() and not line.startswith("#")
        ]

# Development requirements
DEV_REQUIREMENTS = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "black>=23.7.0",
    "flake8>=6.0.0",
    "mypy>=1.5.0",
    "isort>=5.12.0",
    "pre-commit>=3.3.0",
    "coverage>=7.2.0",
]

# Package metadata
PACKAGE_INFO = {
    "name": "webops-agent-system",
    "version": "1.0.0",
    "author": "Douglas Mutethia",
    "author_email": "douglas@eleso.com",
    "description": "AI Agent System for WebOps - Advanced autonomous agent capabilities",
    "long_description": LONG_DESCRIPTION,
    "long_description_content_type": "text/markdown",
    "url": "https://github.com/dagiim/webops",
    "download_url": "https://github.com/dagiim/webops/archive/v1.0.0.tar.gz",
    "project_urls": {
        "Bug Reports": "https://github.com/dagiim/webops/issues",
        "Source": "https://github.com/dagiim/webops",
        "Documentation": "https://webops.docs.eleso.com",
    },
    "license": "MIT",
    "classifiers": [
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Natural Language :: English",
    ],
    "python_requires": ">=3.8",
    "packages": find_packages(exclude=["tests*", "docs*", "examples*"]),
    "include_package_data": True,
    "zip_safe": False,
    "install_requires": REQUIREMENTS,
    "extras_require": {
        "dev": DEV_REQUIREMENTS,
        "ml": [
            "numpy>=1.24.0",
            "scipy>=1.11.0",
            "pandas>=2.0.0",
            "scikit-learn>=1.3.0",
            "torch>=2.0.0",
            "transformers>=4.30.0",
            "tensorflow>=2.13.0",
        ],
        "monitoring": [
            "prometheus-client>=0.17.0",
            "psutil>=5.9.0",
            "nvidia-ml-py>=12.535.0",
        ],
        "api": [
            "fastapi>=0.103.0",
            "uvicorn>=0.23.0",
            "starlette>=0.27.0",
            "httpx>=0.24.0",
        ],
        "database": [
            "sqlalchemy>=2.0.0",
            "alembic>=1.12.0",
            "asyncpg>=0.28.0",
            "aiopg>=1.4.0",
        ],
        "full": [
            "prometheus-client>=0.17.0",
            "psutil>=5.9.0",
            "fastapi>=0.103.0",
            "uvicorn>=0.23.0",
            "sqlalchemy>=2.0.0",
            "numpy>=1.24.0",
            "torch>=2.0.0",
            "transformers>=4.30.0",
        ],
    },
    "entry_points": {
        "console_scripts": [
            "webops-agent=webops.agents.main:main",
            "webops-test=webops.agents.tests.test_runner:main",
            "webops-config=webops.agents.config.config_manager:main",
        ],
        "webops.agents.skills": [
            "communication=communication.base:CommunicationSkill",
            "problem_solving=skills.base_skills:ProblemSolvingSkill",
            "monitoring=skills.base_skills:MonitoringSkill",
            "learning=skills.base_skills:LearningSkill",
        ],
        "webops.agents.memory": [
            "episodic=memory.episodic:EpisodicMemory",
            "semantic=memory.semantic:SemanticMemory",
            "procedural=memory.procedural:ProceduralMemory",
            "learning=memory.learning:LearningMemory",
        ],
        "webops.agents.decision": [
            "planning=decision.planning:PlanningSystem",
            "evaluation=decision.evaluation:DecisionEvaluationSystem",
            "risk_assessment=decision.risk_assessment:RiskAssessment",
            "personality=decision.personality_influence:PersonalityInfluence",
        ],
        "webops.agents.lifecycle": [
            "lifecycle=lifecycle.lifecycle_manager:LifecycleManager",
            "resource=lifecycle.resource_manager:ResourceManager",
        ],
    },
    "keywords": [
        "ai",
        "agent",
        "artificial intelligence",
        "autonomous",
        "webops",
        "deployment",
        "monitoring",
        "automation",
        "skills",
        "memory",
        "decision",
        "communication",
        "lifecycle",
    ],
}

def read_file(filepath):
    """Read file content safely."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

# Additional package configuration
PACKAGE_INFO["data_files"] = [
    ("share/webops/agents/templates", [
        "templates/*.py",
        "templates/*.json",
        "templates/*.yaml",
        "templates/*.yml",
    ]),
    ("share/webops/agents/config", [
        "config/*.yaml",
        "config/*.yml",
        "config/*.json",
    ]),
    ("share/doc/webops/agents", [
        "README.md",
        "docs/*.md",
        "examples/*.py",
    ]),
    ("bin", [
        "scripts/agent",
        "scripts/test",
        "scripts/config",
    ]),
]

# Custom setup for better control
setup(**PACKAGE_INFO)