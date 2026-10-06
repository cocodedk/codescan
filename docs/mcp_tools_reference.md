# CodeScan MCP Tools Reference

This document describes all MCP tools available in `codescan_mcp_server.py` for querying and analyzing the code graph.

---

## Tool List

### 1. `graph_summary`
**Description:**
Returns counts of functions, classes, and calls in the code graph.

**Parameters:** None

**Sample Output:**
```json
[
  {"funcs": 42, "classes": 10, "calls": 123}
]
```

---

### 2. `list_files`
**Description:**
Lists all unique file paths present in the code graph.

**Parameters:** None

**Sample Output:**
```json
[
  {"file": "src/module1.py"},
  {"file": "src/module2.py"}
]
```

---

### 3. `list_functions`
**Description:**
Lists all functions defined in a specific file.

**Parameters:**
- `file` (str): Path to the file

**Sample Output:**
```json
[
  {"name": "foo", "line": 10, "end_line": 20},
  {"name": "bar", "line": 22, "end_line": 30}
]
```

---

### 4. `list_classes`
**Description:**
Lists all classes defined in a specific file.

**Parameters:**
- `file` (str): Path to the file

**Sample Output:**
```json
[
  {"class": "MyClass", "line": 5, "end_line": 50}
]
```

---

### 5. `callees`
**Description:**
Finds functions called by a specific function.

**Parameters:**
- `fn` (str): Name of the function

**Sample Output:**
```json
[
  {"callee": "helper", "caller_file": "src/main.py"}
]
```

---

### 6. `callers`
**Description:**
Finds functions that call a specific function.

**Parameters:**
- `fn` (str): Name of the function

**Sample Output:**
```json
[
  {"caller": "main", "caller_file": "src/main.py"}
]
```

---

### 7. `unresolved_references`
**Description:**
Lists unresolved function references in the codebase.

**Parameters:** None

**Sample Output:**
```json
[
  {"name": "external_func", "first_seen_in": "src/foo.py"}
]
```

---

### 8. `uncalled_functions`
**Description:**
Lists all user-defined functions that are not called by any other function.

**Parameters:** None

**Sample Output:**
```json
[
  {"name": "unused_func", "file": "src/bar.py", "line": 42, "end_line": 45}
]
```

---

### 9. `most_called_functions`
**Description:**
Lists functions with the most callers (fan-in).

**Parameters:**
- `limit` (int, optional): Max results (default 10)

**Sample Output:**
```json
[
  {"name": "foo", "file": "src/a.py", "num_callers": 5}
]
```

---

### 10. `most_calling_functions`
**Description:**
Lists functions that call the most other functions (fan-out).

**Parameters:**
- `limit` (int, optional): Max results (default 10)

**Sample Output:**
```json
[
  {"name": "main", "file": "src/main.py", "num_callees": 8}
]
```

---

### 11. `recursive_functions`
**Description:**
Lists functions that call themselves (direct recursion).

**Parameters:** None

**Sample Output:**
```json
[
  {"name": "factorial", "file": "src/math.py", "line": 12}
]
```

---

### 12. `classes_with_no_methods`
**Description:**
Lists classes that do not contain any methods.

**Parameters:** None

**Sample Output:**
```json
[
  {"class": "EmptyClass", "file": "src/empty.py", "line": 3}
]
```

---

### 13. `functions_calling_references`
**Description:**
Lists functions that call at least one reference function (potential missing dependencies).

**Parameters:** None

**Sample Output:**
```json
[
  {"name": "foo", "file": "src/a.py", "num_reference_calls": 2}
]
```

---

### 14. `classes_with_most_methods`
**Description:**
Lists classes with the most methods.

**Parameters:**
- `limit` (int, optional): Max results (default 10)

**Sample Output:**
```json
[
  {"class": "BigClass", "file": "src/big.py", "num_methods": 12}
]
```

---

### 15. `function_call_arguments`
**Description:**
Lists all argument lists used in calls to a given function.

**Parameters:**
- `fn` (str): Name of the function
- `file` (str, optional): File path to disambiguate

**Sample Output:**
```json
[
  {"args": "x, y", "caller": "main", "caller_file": "src/main.py", "line": 42}
]
```

---

### 16. `rescan_codebase`
**Description:**
Runs `scanner.py` to re-analyze the codebase and repopulate the Neo4j database.

**Parameters:** None

**Sample Output:**
```json
{
  "success": true,
  "output": "...scanner output...",
  "error": null
}
```

---

### 17. `pass_through_functions`
**Description:**
Lists functions whose whole body is one call to another defined function (a layer that can usually be cut). Forwarders whose call stayed unresolved are not listed. `same_arguments` is true when the call passes exactly the forwarder's own parameters, in order, by name.

**Parameters:** None

**Sample Output:**
```json
[
  {"name": "a", "file": "src/foo.py", "line": 3, "target": "b", "target_file": "src/foo.py", "callers": 2, "same_arguments": true}
]
```
