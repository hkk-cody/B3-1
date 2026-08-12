import ast
import os
import unittest


class BuiltinCollectionConstraintTests(unittest.TestCase):
    def test_product_code_does_not_use_forbidden_collections(self):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        product_paths = [os.path.join(project_root, "main.py")]
        package_root = os.path.join(project_root, "mini_redis")
        for filename in os.listdir(package_root):
            if filename.endswith(".py"):
                product_paths.append(os.path.join(package_root, filename))

        violations = []
        for path in product_paths:
            with open(path, "r", encoding="utf-8") as source_file:
                tree = ast.parse(source_file.read(), filename=path)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Dict, ast.Set)):
                    violations.append((path, node.lineno, type(node).__name__))
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in ("dict", "set")
                ):
                    violations.append((path, node.lineno, node.func.id + "()"))
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "collections":
                            violations.append((path, node.lineno, "collections"))
                if isinstance(node, ast.ImportFrom) and node.module == "collections":
                    violations.append((path, node.lineno, "collections"))

        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
