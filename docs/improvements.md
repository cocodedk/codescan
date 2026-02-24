# CodeScan Improvements

## Pending Tasks

~~1. **Class length not implemented** (from tasks/todo.md:10)~~
   - ~~Function length is done (stored in function nodes)~~
   - ~~Class length needs to be added to class nodes~~
   - ~~Would require calculating `end_line - line + 1` for ClassDef nodes~~ ✅ DONE

~~2. **Circular import workaround**~~
   - ~~`analyzer.py:22-23` has duplicate `_is_example_file` function to avoid circular imports~~
   - ~~Should be refactored into a shared utility~~ ✅ DONE

## Code Quality

~~3. **Type hints** - Add comprehensive type hints throughout the codebase~~ ✅ DONE (analyzer.py)
4. **Error handling** - Some areas lack proper exception handling
5. **DRY violations** - Duplicate code patterns between modules

## Performance

6. **Batch Neo4j operations** - Currently running individual queries; batch operations would speed up large codebases
7. **Caching** - Add caching for repeated queries in MCP tools

## Features

8. **Complexity metrics** - Add cyclomatic complexity, cognitive complexity detection
9. **Code smell detection** - Detect common anti-patterns (long parameter lists, god objects, etc.)
10. **Import analysis** - Map import relationships between files/modules
11. **Decorator tracking** - Track and label functions/classes with decorators

## Testing

12. **Run the test suite** - Verify all tests pass and add coverage for missing areas
13. **Add integration tests** for Neo4j operations
14. **Mock Neo4j** - Use mocks instead of requiring live database for unit tests

## Documentation

15. **API documentation** - Add docstrings to all MCP tools
16. **Contributing guide** - If open source
17. **Architecture diagram** - Visual overview of components

## Minor Enhancements

~~18. **Configurable dunder method handling** - Allow skipping/treating dunder methods via config~~ ✅ DONE
19. **Async support** - Consider async Neo4j operations for better throughput
20. **Incremental scanning** - Only update changed files instead of full rescan
