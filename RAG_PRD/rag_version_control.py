"""
RAG Optimization Version Control System
Provides version tagging, rollback, metrics tracking, and promotion policies
"""

import json
import shutil
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import subprocess

# Paths
VERSIONS_FILE = "rag_versions.json"
CONFIG_FILE = "memory/vector_store.py"
BACKUP_DIR = "backups/rag_versions/"
METRICS_HISTORY = "rag_metrics_history.json"

class RAGVersionControl:
    """Manage RAG optimization versions with rollback capability"""
    
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.versions_file = self.base_dir / VERSIONS_FILE
        self.config_file = self.base_dir / CONFIG_FILE
        self.backup_dir = self.base_dir / BACKUP_DIR
        self.metrics_file = self.base_dir / METRICS_HISTORY
        
        # Create directories
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize files if they don't exist
        if not self.versions_file.exists():
            self._init_versions_file()
        if not self.metrics_file.exists():
            self._init_metrics_file()
    
    def _init_versions_file(self):
        """Initialize versions tracking file"""
        initial_data = {
            "current_version": "alpha-v3",
            "versions": []
        }
        with open(self.versions_file, 'w') as f:
            json.dump(initial_data, f, indent=2)
    
    def _init_metrics_file(self):
        """Initialize metrics history file"""
        with open(self.metrics_file, 'w') as f:
            json.dump([], f, indent=2)
    
    def save_version(
        self,
        version_name: str,
        relevance: float,
        alpha: float,
        tests_passed: int = 5,
        total_tests: int = 13,
        precision: float = 32.95,
        recall: float = 92.31,
        f1_score: float = 47.51,
        notes: str = "",
        enable_reranking: bool = False,
        tags: List[str] = None
    ):
        """
        Save a version snapshot with full metrics
        
        Args:
            version_name: Semantic version ID (e.g., 'alpha-v3')
            relevance: Average relevance score (%)
            alpha: Hybrid vector weight (0-1)
            tests_passed: Number of tests passed
            total_tests: Total number of tests
            precision: Average precision (%)
            recall: Average recall (%)
            f1_score: Average F1 score (%)
            notes: Description of changes
            enable_reranking: Whether reranking is enabled
            tags: Additional tags (e.g., ['stable', 'production'])
        """
        print(f"\n{'='*70}")
        print(f"SAVING VERSION: {version_name}")
        print(f"{'='*70}")
        
        # Create backup of config file
        backup_path = self.backup_dir / f"{version_name}_vector_store.py"
        if self.config_file.exists():
            shutil.copy(self.config_file, backup_path)
            print(f"✅ Config backed up to: {backup_path}")
        else:
            print(f"⚠️  Config file not found: {self.config_file}")
        
        # Create version data
        version_data = {
            "version": version_name,
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "relevance": relevance,
                "tests_passed": tests_passed,
                "total_tests": total_tests,
                "precision": precision,
                "recall": recall,
                "f1_score": f1_score
            },
            "configuration": {
                "alpha": alpha,
                "vector_weight": alpha,
                "lexical_weight": round(1 - alpha, 2),
                "enable_reranking": enable_reranking
            },
            "notes": notes,
            "tags": tags or []
        }
        
        # Load and update versions file
        with open(self.versions_file, 'r') as f:
            data = json.load(f)
        
        data["versions"].append(version_data)
        data["current_version"] = version_name
        
        with open(self.versions_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✅ Version saved: {version_name}")
        print(f"   Relevance:    {relevance:.2f}%")
        print(f"   Tests Passed: {tests_passed}/{total_tests}")
        print(f"   Alpha:        {alpha:.2f}")
        print(f"{'='*70}\n")
        
        return version_data
    
    def rollback(self, version_name: str, dry_run: bool = False):
        """
        Rollback to a previous version
        
        Args:
            version_name: Version to rollback to (e.g., 'alpha-v2')
            dry_run: If True, only show what would be done without making changes
        """
        print(f"\n{'='*70}")
        print(f"ROLLBACK TO: {version_name}")
        print(f"{'='*70}")
        
        backup_path = self.backup_dir / f"{version_name}_vector_store.py"
        
        if not backup_path.exists():
            print(f"❌ ERROR: Version '{version_name}' not found")
            print(f"   Backup file missing: {backup_path}")
            self.list_versions()
            return False
        
        # Get version info
        version_info = self.get_version_info(version_name)
        if version_info:
            print(f"\n📋 Version Info:")
            print(f"   Timestamp:    {version_info['timestamp']}")
            print(f"   Relevance:    {version_info['metrics']['relevance']:.2f}%")
            print(f"   Alpha:        {version_info['configuration']['alpha']:.2f}")
            print(f"   Notes:        {version_info['notes']}")
        
        if dry_run:
            print(f"\n🔍 DRY RUN - No changes made")
            print(f"   Would copy: {backup_path}")
            print(f"   To:         {self.config_file}")
            return True
        
        # Create backup of current config before rollback
        current_backup = self.backup_dir / f"pre_rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}_vector_store.py"
        if self.config_file.exists():
            shutil.copy(self.config_file, current_backup)
            print(f"\n💾 Current config backed up to: {current_backup}")
        
        # Perform rollback
        shutil.copy(backup_path, self.config_file)
        
        # Update current version
        with open(self.versions_file, 'r') as f:
            data = json.load(f)
        data["current_version"] = version_name
        with open(self.versions_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n✅ Successfully rolled back to {version_name}")
        print(f"{'='*70}\n")
        
        return True
    
    def get_version_info(self, version_name: str) -> Optional[Dict]:
        """Get information about a specific version"""
        with open(self.versions_file, 'r') as f:
            data = json.load(f)
        
        for version in data["versions"]:
            if version["version"] == version_name:
                return version
        return None
    
    def list_versions(self, verbose: bool = False):
        """List all saved versions"""
        with open(self.versions_file, 'r') as f:
            data = json.load(f)
        
        current = data.get("current_version", "unknown")
        versions = data.get("versions", [])
        
        print(f"\n{'='*70}")
        print(f"RAG OPTIMIZATION VERSION HISTORY")
        print(f"{'='*70}")
        print(f"Current Version: {current}")
        print(f"Total Versions:  {len(versions)}")
        print(f"{'='*70}\n")
        
        if not versions:
            print("No versions saved yet.")
            return
        
        # Table header
        print(f"{'Version':<15} {'Date':<12} {'Relevance':<10} {'Alpha':<8} {'Tests':<8} {'Status':<10}")
        print("-"*70)
        
        for v in versions:
            version_name = v["version"]
            date = datetime.fromisoformat(v["timestamp"]).strftime("%Y-%m-%d")
            relevance = v["metrics"]["relevance"]
            alpha = v["configuration"]["alpha"]
            tests = f"{v['metrics']['tests_passed']}/{v['metrics']['total_tests']}"
            status = "CURRENT" if version_name == current else ""
            
            print(f"{version_name:<15} {date:<12} {relevance:>6.2f}%    {alpha:<8.2f} {tests:<8} {status:<10}")
        
        if verbose:
            print("\n" + "="*70)
            print("DETAILED VERSION INFORMATION")
            print("="*70 + "\n")
            
            for v in versions:
                print(f"📦 {v['version']}")
                print(f"   Timestamp:    {v['timestamp']}")
                print(f"   Relevance:    {v['metrics']['relevance']:.2f}%")
                print(f"   Tests Passed: {v['metrics']['tests_passed']}/{v['metrics']['total_tests']}")
                print(f"   Precision:    {v['metrics']['precision']:.2f}%")
                print(f"   Recall:       {v['metrics']['recall']:.2f}%")
                print(f"   F1 Score:     {v['metrics']['f1_score']:.2f}%")
                print(f"   Alpha:        {v['configuration']['alpha']:.2f}")
                print(f"   Reranking:    {v['configuration']['enable_reranking']}")
                print(f"   Notes:        {v['notes']}")
                if v.get('tags'):
                    print(f"   Tags:         {', '.join(v['tags'])}")
                print()
    
    def promote_version(
        self,
        version_name: str,
        criteria: Dict[str, Any] = None,
        tags: List[str] = None
    ) -> bool:
        """
        Promote a version based on criteria
        
        Args:
            version_name: Version to promote
            criteria: Promotion criteria to check
            tags: Tags to add (e.g., ['stable', 'production'])
        
        Returns:
            True if promotion criteria met, False otherwise
        """
        print(f"\n{'='*70}")
        print(f"PROMOTION EVALUATION: {version_name}")
        print(f"{'='*70}")
        
        version_info = self.get_version_info(version_name)
        if not version_info:
            print(f"❌ ERROR: Version '{version_name}' not found")
            return False
        
        # Default criteria
        default_criteria = {
            "min_relevance_gain": 0.5,  # Minimum 0.5pp improvement
            "no_test_regression": True,  # Must not lose tests
            "min_relevance": 70.0,       # Minimum absolute relevance
        }
        
        criteria = criteria or default_criteria
        
        # Get previous version for comparison
        with open(self.versions_file, 'r') as f:
            data = json.load(f)
        
        versions = data["versions"]
        current_idx = next((i for i, v in enumerate(versions) if v["version"] == version_name), -1)
        
        if current_idx <= 0:
            print("⚠️  No previous version to compare against")
            previous_version = None
        else:
            previous_version = versions[current_idx - 1]
        
        # Evaluate criteria
        print("\n📋 PROMOTION CRITERIA EVALUATION:")
        print("-"*70)
        
        passes = []
        
        # Check relevance gain
        if previous_version:
            relevance_gain = version_info["metrics"]["relevance"] - previous_version["metrics"]["relevance"]
            min_gain = criteria.get("min_relevance_gain", 0.5)
            passed = relevance_gain >= min_gain
            passes.append(passed)
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} Relevance Gain:     {relevance_gain:+.2f}pp (required: ≥{min_gain:+.2f}pp)")
        
        # Check test regression
        if previous_version and criteria.get("no_test_regression"):
            test_diff = version_info["metrics"]["tests_passed"] - previous_version["metrics"]["tests_passed"]
            passed = test_diff >= 0
            passes.append(passed)
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} Test Regression:    {test_diff:+d} tests (required: no regression)")
        
        # Check minimum relevance
        min_relevance = criteria.get("min_relevance", 70.0)
        passed = version_info["metrics"]["relevance"] >= min_relevance
        passes.append(passed)
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} Minimum Relevance:  {version_info['metrics']['relevance']:.2f}% (required: ≥{min_relevance:.2f}%)")
        
        # Check documentation
        has_notes = bool(version_info.get("notes", "").strip())
        passes.append(has_notes)
        status = "✅ PASS" if has_notes else "❌ FAIL"
        print(f"{status} Documentation:      {'Complete' if has_notes else 'Missing'}")
        
        print("-"*70)
        
        # Final decision
        all_passed = all(passes)
        
        if all_passed:
            print(f"\n✅ PROMOTION APPROVED: {version_name}")
            
            # Add tags
            if tags:
                version_info["tags"] = list(set(version_info.get("tags", []) + tags))
                with open(self.versions_file, 'w') as f:
                    json.dump(data, f, indent=2)
                print(f"   Tags added: {', '.join(tags)}")
        else:
            print(f"\n❌ PROMOTION DENIED: {version_name}")
            print(f"   Criteria passed: {sum(passes)}/{len(passes)}")
        
        print(f"{'='*70}\n")
        
        return all_passed
    
    def compare_versions(self, version1: str, version2: str):
        """Compare two versions side by side"""
        v1_info = self.get_version_info(version1)
        v2_info = self.get_version_info(version2)
        
        if not v1_info or not v2_info:
            print(f"❌ ERROR: One or both versions not found")
            return
        
        print(f"\n{'='*70}")
        print(f"VERSION COMPARISON: {version1} vs {version2}")
        print(f"{'='*70}\n")
        
        print(f"{'Metric':<20} {version1:<15} {version2:<15} {'Delta':<15}")
        print("-"*70)
        
        # Relevance
        rel1 = v1_info["metrics"]["relevance"]
        rel2 = v2_info["metrics"]["relevance"]
        delta = rel2 - rel1
        print(f"{'Relevance':<20} {rel1:>6.2f}%{' '*8} {rel2:>6.2f}%{' '*8} {delta:>+6.2f}%")
        
        # Tests Passed
        tests1 = v1_info["metrics"]["tests_passed"]
        tests2 = v2_info["metrics"]["tests_passed"]
        delta = tests2 - tests1
        print(f"{'Tests Passed':<20} {tests1:>6d}{' '*9} {tests2:>6d}{' '*9} {delta:>+6d}")
        
        # Alpha
        alpha1 = v1_info["configuration"]["alpha"]
        alpha2 = v2_info["configuration"]["alpha"]
        delta = alpha2 - alpha1
        print(f"{'Alpha':<20} {alpha1:>6.2f}{' '*9} {alpha2:>6.2f}{' '*9} {delta:>+6.2f}")
        
        # Precision
        prec1 = v1_info["metrics"]["precision"]
        prec2 = v2_info["metrics"]["precision"]
        delta = prec2 - prec1
        print(f"{'Precision':<20} {prec1:>6.2f}%{' '*8} {prec2:>6.2f}%{' '*8} {delta:>+6.2f}%")
        
        # Recall
        rec1 = v1_info["metrics"]["recall"]
        rec2 = v2_info["metrics"]["recall"]
        delta = rec2 - rec1
        print(f"{'Recall':<20} {rec1:>6.2f}%{' '*8} {rec2:>6.2f}%{' '*8} {delta:>+6.2f}%")
        
        # F1 Score
        f11 = v1_info["metrics"]["f1_score"]
        f12 = v2_info["metrics"]["f1_score"]
        delta = f12 - f11
        print(f"{'F1 Score':<20} {f11:>6.2f}%{' '*8} {f12:>6.2f}%{' '*8} {delta:>+6.2f}%")
        
        print()
    
    def export_history(self, output_file: str = "rag_optimization_history.csv"):
        """Export version history to CSV for analysis"""
        import csv
        
        with open(self.versions_file, 'r') as f:
            data = json.load(f)
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "Version", "Timestamp", "Relevance", "Tests_Passed", "Total_Tests",
                "Precision", "Recall", "F1_Score", "Alpha", "Reranking", "Notes"
            ])
            
            for v in data["versions"]:
                writer.writerow([
                    v["version"],
                    v["timestamp"],
                    v["metrics"]["relevance"],
                    v["metrics"]["tests_passed"],
                    v["metrics"]["total_tests"],
                    v["metrics"]["precision"],
                    v["metrics"]["recall"],
                    v["metrics"]["f1_score"],
                    v["configuration"]["alpha"],
                    v["configuration"]["enable_reranking"],
                    v["notes"]
                ])
        
        print(f"✅ History exported to: {output_file}")


def main():
    """CLI interface for version control"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG Optimization Version Control")
    parser.add_argument("command", choices=["save", "rollback", "list", "promote", "compare", "export"],
                       help="Command to execute")
    parser.add_argument("--version", help="Version name (e.g., alpha-v3)")
    parser.add_argument("--relevance", type=float, help="Relevance score")
    parser.add_argument("--alpha", type=float, help="Alpha value")
    parser.add_argument("--tests-passed", type=int, default=5, help="Tests passed")
    parser.add_argument("--notes", default="", help="Version notes")
    parser.add_argument("--tags", nargs="+", help="Tags to add")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (no changes)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--version2", help="Second version for comparison")
    
    args = parser.parse_args()
    
    vc = RAGVersionControl()
    
    if args.command == "save":
        if not args.version or args.relevance is None or args.alpha is None:
            print("❌ ERROR: --version, --relevance, and --alpha required for save")
            return
        vc.save_version(
            version_name=args.version,
            relevance=args.relevance,
            alpha=args.alpha,
            tests_passed=args.tests_passed,
            notes=args.notes,
            tags=args.tags
        )
    
    elif args.command == "rollback":
        if not args.version:
            print("❌ ERROR: --version required for rollback")
            return
        vc.rollback(args.version, dry_run=args.dry_run)
    
    elif args.command == "list":
        vc.list_versions(verbose=args.verbose)
    
    elif args.command == "promote":
        if not args.version:
            print("❌ ERROR: --version required for promote")
            return
        vc.promote_version(args.version, tags=args.tags)
    
    elif args.command == "compare":
        if not args.version or not args.version2:
            print("❌ ERROR: --version and --version2 required for compare")
            return
        vc.compare_versions(args.version, args.version2)
    
    elif args.command == "export":
        vc.export_history()


if __name__ == "__main__":
    main()
