"""Java buildpack detector."""

from pathlib import Path
from typing import Optional
from .base import Buildpack, BuildpackResult


class JavaBuildpack(Buildpack):
    """Detect and configure Java applications."""

    name = 'java'
    display_name = 'Java'

    def detect(self, repo_path: Path) -> BuildpackResult:
        """Detect Java project."""
        # Check for build files
        has_maven = (repo_path / 'pom.xml').exists()
        has_gradle = (repo_path / 'build.gradle').exists() or (repo_path / 'build.gradle.kts').exists()
        has_gradlew = (repo_path / 'gradlew').exists()

        if not (has_maven or has_gradle):
            return BuildpackResult(
                detected=False,
                buildpack_name=self.name,
                project_type='java',
                confidence=0.0
            )

        # Detect framework
        framework, confidence = self._detect_framework(repo_path, has_maven, has_gradle)

        # Detect Java version
        java_version = self._detect_java_version(repo_path, has_maven, has_gradle)

        # Determine build tool
        if has_maven:
            build_tool = 'maven'
            install_cmd = './mvnw clean install -DskipTests' if (repo_path / 'mvnw').exists() else 'mvn clean install -DskipTests'
            build_cmd = './mvnw package -DskipTests' if (repo_path / 'mvnw').exists() else 'mvn package -DskipTests'
        else:
            build_tool = 'gradle'
            install_cmd = './gradlew build -x test' if has_gradlew else 'gradle build -x test'
            build_cmd = install_cmd

        # Determine start command
        start_cmd = self._get_start_command(framework, has_maven, has_gradle)

        # Determine port
        port = 8080
        if framework == 'spring-boot':
            port = 8080
        elif framework == 'quarkus':
            port = 8080
        elif framework == 'micronaut':
            port = 8080

        return BuildpackResult(
            detected=True,
            buildpack_name=self.name,
            project_type='java',
            confidence=confidence,
            framework=framework,
            version=java_version,
            build_command=build_cmd,
            start_command=start_cmd,
            install_command=install_cmd,
            package_manager=build_tool,
            port=port,
            env_vars={
                'JAVA_OPTS': '-Xmx512m -Xms256m',
            },
            metadata={
                'build_tool': build_tool,
                'has_wrapper': has_gradlew or (repo_path / 'mvnw').exists(),
            }
        )

    def _detect_framework(self, repo_path: Path, has_maven: bool, has_gradle: bool) -> tuple[str, float]:
        """Detect Java framework."""
        # Check pom.xml for Spring Boot
        if has_maven:
            pom_content = self._read_file(repo_path / 'pom.xml')
            if pom_content:
                if 'spring-boot' in pom_content.lower():
                    return 'spring-boot', 0.95
                if 'quarkus' in pom_content.lower():
                    return 'quarkus', 0.95
                if 'micronaut' in pom_content.lower():
                    return 'micronaut', 0.95

        # Check build.gradle for Spring Boot
        if has_gradle:
            for gradle_file in ['build.gradle', 'build.gradle.kts']:
                gradle_path = repo_path / gradle_file
                if gradle_path.exists():
                    gradle_content = self._read_file(gradle_path)
                    if gradle_content:
                        if 'org.springframework.boot' in gradle_content:
                            return 'spring-boot', 0.95
                        if 'io.quarkus' in gradle_content:
                            return 'quarkus', 0.95
                        if 'io.micronaut' in gradle_content:
                            return 'micronaut', 0.95

        # Generic Java
        return 'java', 0.80

    def _detect_java_version(self, repo_path: Path, has_maven: bool, has_gradle: bool) -> str:
        """Detect Java version."""
        # Check pom.xml
        if has_maven:
            pom_content = self._read_file(repo_path / 'pom.xml')
            if pom_content:
                import re
                # Look for java.version property
                version_match = re.search(r'<java\.version>(\d+)</java\.version>', pom_content)
                if version_match:
                    return version_match.group(1)
                # Look for maven.compiler.source
                source_match = re.search(r'<maven\.compiler\.source>(\d+)</maven\.compiler\.source>', pom_content)
                if source_match:
                    return source_match.group(1)

        # Check build.gradle
        if has_gradle:
            for gradle_file in ['build.gradle', 'build.gradle.kts']:
                gradle_path = repo_path / gradle_file
                if gradle_path.exists():
                    gradle_content = self._read_file(gradle_path)
                    if gradle_content:
                        import re
                        source_match = re.search(r'sourceCompatibility\s*=\s*["\']?(\d+)["\']?', gradle_content)
                        if source_match:
                            return source_match.group(1)

        # Default to Java 17 (LTS)
        return '17'

    def _get_start_command(self, framework: str, has_maven: bool, has_gradle: bool) -> str:
        """Get start command."""
        if framework == 'spring-boot':
            if has_maven:
                return 'java -jar target/*.jar'
            else:
                return 'java -jar build/libs/*.jar'
        elif framework in ['quarkus', 'micronaut']:
            if has_maven:
                return 'java -jar target/*-runner.jar'
            else:
                return 'java -jar build/libs/*-runner.jar'
        else:
            # Generic Java application
            if has_maven:
                return 'java -jar target/*.jar'
            else:
                return 'java -jar build/libs/*.jar'
