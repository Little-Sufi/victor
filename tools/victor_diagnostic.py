
"""
VICTOR Comprehensive Diagnostic & Testing Tool
Tests all skills, components, detects errors, validates everything!
"""
import os
import sys
import time
import json
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class VictorDiagnosticTool:
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'core_components': {},
            'skills': {},
            'errors': [],
            'warnings': [],
            'summary': {}
        }
        self.victor = None

    def run_full_diagnostic(self):
        print("="*80)
        print("VICTOR COMPREHENSIVE DIAGNOSTIC & TESTING TOOL")
        print("="*80)
        print(f"\nStarting diagnostic at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        print("\n" + "="*80)
        print("STEP 1: TESTING CORE MODULES")
        print("="*80)
        self._test_core_modules()

        print("\n" + "="*80)
        print("STEP 2: TESTING OS LAYER")
        print("="*80)
        self._test_os_layer()

        print("\n" + "="*80)
        print("STEP 3: INITIALIZING VICTOR & TESTING SYSTEMS")
        print("="*80)
        self._test_victor_initialization()

        print("\n" + "="*80)
        print("STEP 4: TESTING ALL SKILLS")
        print("="*80)
        self._test_all_skills()

        print("\n" + "="*80)
        print("STEP 5: GENERATING REPORT")
        print("="*80)
        self._generate_report()

        return self.results

    def _test_core_modules(self):
        print("\nTesting core modules compilation...")
        core_modules = [
            'core.brain',
            'core.memory',
            'core.vision',
            'core.voice',
            'core.security',
            'core.autonomous_agent',
            'core.intent_classifier',
            'core.victor_core'
        ]

        for module_name in core_modules:
            try:
                __import__(module_name)
                print(f"  [OK] {module_name}")
                self.results['core_components'][module_name] = 'OK'
            except Exception as e:
                error_msg = f"Error in {module_name}: {str(e)}"
                print(f"  [FAIL] {module_name} - ERROR: {str(e)}")
                self.results['errors'].append(error_msg)
                self.results['core_components'][module_name] = 'ERROR'

    def _test_os_layer(self):
        print("\nTesting OS layer...")
        os_modules = [
            'os_layer.base',
            'os_layer.factory',
            'os_layer.windows',
            'os_layer.linux'
        ]

        for module_name in os_modules:
            try:
                __import__(module_name)
                print(f"  [OK] {module_name}")
            except Exception as e:
                error_msg = f"Error in {module_name}: {str(e)}"
                print(f"  [FAIL] {module_name} - ERROR: {str(e)}")
                self.results['errors'].append(error_msg)

    def _test_victor_initialization(self):
        print("\nInitializing Victor...")
        try:
            from core.victor_core import VictorCore
            self.victor = VictorCore()
            print("  [OK] Victor initialized successfully")

            systems = ['voice', 'vision', 'brain', 'memory', 'security', 'os_layer']
            for system in systems:
                if hasattr(self.victor, system):
                    print(f"  [OK] {system} system loaded")
                else:
                    warning_msg = f"{system} system not found"
                    print(f"  [WARN] {warning_msg}")
                    self.results['warnings'].append(warning_msg)

            skill_count = len(self.victor.skills)
            print(f"  [OK] {skill_count} skills loaded")
            self.results['skills']['loaded_count'] = skill_count

        except Exception as e:
            error_msg = f"Victor initialization failed: {str(e)}"
            print(f"  [FAIL] {error_msg}")
            self.results['errors'].append(error_msg)

    def _test_all_skills(self):
        if not self.victor:
            print("\nSkipping skill tests - Victor not initialized")
            return

        print(f"\nTesting {len(self.victor.skills)} skills...")

        test_prompts = {
            'system_control': [
                "What time is it?",
                "What's today's date?",
                "Show system info"
            ],
            'file_manager': [
                "List directory",
                "Search for .py files"
            ],
            'terminal': [
                "Run command echo hello",
                "List directory"
            ],
            'cooking': [
                "Give me a recipe for pasta",
                "Convert 1 cup to grams"
            ]
        }

        for skill_id, skill in self.victor.skills.items():
            print(f"\n  Testing skill: {skill_id}")
            try:
                if hasattr(skill, 'can_handle') and hasattr(skill, 'handle'):
                    print(f"    [OK] Skill methods present")

                    if skill_id in test_prompts:
                        for prompt in test_prompts[skill_id]:
                            try:
                                can_handle = skill.can_handle(prompt)
                                print(f"    [OK] can_handle('{prompt}'): {can_handle:.2f}")

                                if can_handle > 0.5:
                                    result = skill.handle(prompt)
                                    result_str = str(result)[:100]
                                    print(f"    [OK] handle() returned: {result_str}...")
                            except Exception as e:
                                warning_msg = f"Skill {skill_id} prompt test failed: {str(e)}"
                                print(f"    [WARN] {warning_msg}")
                                self.results['warnings'].append(warning_msg)

                    self.results['skills'][skill_id] = 'OK'
                else:
                    warning_msg = f"Skill {skill_id} missing methods"
                    print(f"    [WARN] {warning_msg}")
                    self.results['warnings'].append(warning_msg)
                    self.results['skills'][skill_id] = 'WARNING'
            except Exception as e:
                error_msg = f"Skill {skill_id} test failed: {str(e)}"
                print(f"    [FAIL] {error_msg}")
                self.results['errors'].append(error_msg)
                self.results['skills'][skill_id] = 'ERROR'

    def _generate_report(self):
        print("\nGenerating final report...")

        error_count = len(self.results['errors'])
        warning_count = len(self.results['warnings'])

        print("\n" + "="*80)
        print("DIAGNOSTIC SUMMARY")
        print("="*80)
        print(f"Errors found: {error_count}")
        print(f"Warnings found: {warning_count}")

        if error_count == 0:
            print("\n[OK] NO ERRORS FOUND!")
            self.results['summary']['status'] = 'ALL_CLEAR'
        else:
            print("\n[FAIL] ERRORS FOUND - PLEASE RESOLVE!")
            self.results['summary']['status'] = 'ERRORS_FOUND'

        if self.results['errors']:
            print("\n" + "="*80)
            print("ERRORS:")
            print("="*80)
            for i, error in enumerate(self.results['errors'], 1):
                print(f"{i}. {error}")

        if self.results['warnings']:
            print("\n" + "="*80)
            print("WARNINGS:")
            print("="*80)
            for i, warning in enumerate(self.results['warnings'], 1):
                print(f"{i}. {warning}")

        report_path = os.path.join(os.path.dirname(__file__), '..', 'diagnostic_report.json')
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n[OK] Report saved to: {report_path}")

        print("\n" + "="*80)
        print("DIAGNOSTIC COMPLETE!")
        print("="*80)


def main():
    tool = VictorDiagnosticTool()
    tool.run_full_diagnostic()


if __name__ == "__main__":
    main()

