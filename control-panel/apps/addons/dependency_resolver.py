"""
Dependency resolution for addon installation order.

Uses topological sort to determine correct installation order
and detect circular dependencies.
"""

from typing import Dict, List, Set
from collections import defaultdict, deque

from .logging_config import get_logger

logger = get_logger(__name__)


class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected."""
    pass


class DependencyNotFoundError(Exception):
    """Raised when a required dependency is not available."""
    pass


class DependencyResolver:
    """
    Resolves addon dependencies using topological sort.

    Determines correct installation order and detects circular dependencies.
    """

    def resolve_install_order(
        self,
        addon_name: str,
        dependency_graph: Dict[str, List[str]]
    ) -> List[str]:
        """
        Resolve installation order for an addon and its dependencies.

        Args:
            addon_name: Name of addon to install
            dependency_graph: Dict mapping addon names to their dependencies

        Returns:
            List of addon names in installation order

        Raises:
            CircularDependencyError: If circular dependencies detected
            DependencyNotFoundError: If required dependency not available
        """
        # Check if addon exists in graph
        if addon_name not in dependency_graph:
            raise DependencyNotFoundError(
                f'Addon {addon_name} not found in dependency graph'
            )

        # Get all addons that need to be installed (addon + dependencies)
        required_addons = self._get_all_dependencies(addon_name, dependency_graph)

        # Build subgraph with only required addons
        subgraph = {
            name: dependency_graph[name]
            for name in required_addons
            if name in dependency_graph
        }

        # Perform topological sort
        sorted_order = self._topological_sort(subgraph)

        logger.debug(
            'Resolved installation order',
            addon_name=addon_name,
            install_order=sorted_order,
            dependency_count=len(sorted_order) - 1
        )

        return sorted_order

    def _get_all_dependencies(
        self,
        addon_name: str,
        dependency_graph: Dict[str, List[str]],
        visited: Set[str] = None
    ) -> Set[str]:
        """
        Get all dependencies recursively (DFS).

        Args:
            addon_name: Starting addon
            dependency_graph: Full dependency graph
            visited: Set of already visited addons (for cycle detection)

        Returns:
            Set of all required addon names

        Raises:
            CircularDependencyError: If circular dependency detected
        """
        if visited is None:
            visited = set()

        if addon_name in visited:
            # We've seen this addon in current path - circular dependency!
            raise CircularDependencyError(
                f'Circular dependency detected involving {addon_name}'
            )

        # Add to current path
        visited.add(addon_name)

        # Start with this addon
        all_deps = {addon_name}

        # Get direct dependencies
        if addon_name in dependency_graph:
            for dep in dependency_graph[addon_name]:
                if dep not in dependency_graph:
                    raise DependencyNotFoundError(
                        f'Dependency {dep} (required by {addon_name}) not found'
                    )

                # Recursively get dependencies of this dependency
                dep_deps = self._get_all_dependencies(
                    dep,
                    dependency_graph,
                    visited.copy()  # Copy to prevent false circular detection
                )
                all_deps.update(dep_deps)

        return all_deps

    def _topological_sort(self, graph: Dict[str, List[str]]) -> List[str]:
        """
        Perform topological sort using Kahn's algorithm.

        Args:
            graph: Dependency graph (node -> list of dependencies)

        Returns:
            List of nodes in topological order

        Raises:
            CircularDependencyError: If cycle detected
        """
        # Calculate in-degrees (number of dependencies)
        in_degree = defaultdict(int)
        for node in graph:
            in_degree[node] = 0

        for node, deps in graph.items():
            for dep in deps:
                in_degree[dep] += 1

        # Queue of nodes with no dependencies
        queue = deque([node for node in graph if in_degree[node] == 0])

        sorted_order = []

        while queue:
            # Remove a node with no dependencies
            node = queue.popleft()
            sorted_order.append(node)

            # For each dependent, reduce in-degree
            for other_node, deps in graph.items():
                if node in deps:
                    in_degree[other_node] -= 1

                    # If all dependencies satisfied, add to queue
                    if in_degree[other_node] == 0:
                        queue.append(other_node)

        # If we couldn't sort all nodes, there's a cycle
        if len(sorted_order) != len(graph):
            unsorted = set(graph.keys()) - set(sorted_order)
            raise CircularDependencyError(
                f'Circular dependency detected in: {unsorted}'
            )

        # Reverse to get installation order (dependencies first)
        return list(reversed(sorted_order))

    def detect_circular_dependencies(
        self,
        dependency_graph: Dict[str, List[str]]
    ) -> List[List[str]]:
        """
        Detect all circular dependencies in the graph.

        Args:
            dependency_graph: Full dependency graph

        Returns:
            List of circular dependency chains
        """
        cycles = []

        def dfs(node: str, path: List[str], visited: Set[str]):
            """DFS to find cycles."""
            if node in visited:
                # Found a cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]

                # Check if we've already found this cycle
                if cycle not in cycles and cycle[::-1] not in cycles:
                    cycles.append(cycle)
                return

            visited.add(node)
            path.append(node)

            if node in dependency_graph:
                for dep in dependency_graph[node]:
                    dfs(dep, path.copy(), visited.copy())

        # Check from each node
        for start_node in dependency_graph:
            dfs(start_node, [], set())

        return cycles

    def get_dependency_tree(
        self,
        addon_name: str,
        dependency_graph: Dict[str, List[str]],
        visited: Set[str] = None
    ) -> Dict[str, Any]:
        """
        Build a tree structure showing dependencies.

        Args:
            addon_name: Root addon
            dependency_graph: Full dependency graph
            visited: Set of visited addons (prevents infinite recursion)

        Returns:
            Nested dict representing dependency tree
        """
        if visited is None:
            visited = set()

        if addon_name in visited:
            return {'name': addon_name, 'circular': True, 'dependencies': []}

        visited.add(addon_name)

        tree = {
            'name': addon_name,
            'dependencies': []
        }

        if addon_name in dependency_graph:
            for dep in dependency_graph[addon_name]:
                dep_tree = self.get_dependency_tree(
                    dep,
                    dependency_graph,
                    visited.copy()
                )
                tree['dependencies'].append(dep_tree)

        return tree

    def validate_graph(self, dependency_graph: Dict[str, List[str]]) -> List[str]:
        """
        Validate dependency graph and return list of issues.

        Args:
            dependency_graph: Full dependency graph

        Returns:
            List of validation error messages
        """
        issues = []

        # Check for circular dependencies
        try:
            cycles = self.detect_circular_dependencies(dependency_graph)
            if cycles:
                for cycle in cycles:
                    issues.append(
                        f'Circular dependency: {" -> ".join(cycle)}'
                    )
        except Exception as e:
            issues.append(f'Error detecting cycles: {str(e)}')

        # Check for missing dependencies
        all_deps = set()
        for deps in dependency_graph.values():
            all_deps.update(deps)

        missing = all_deps - set(dependency_graph.keys())
        if missing:
            issues.append(
                f'Missing addon definitions: {", ".join(missing)}'
            )

        return issues
