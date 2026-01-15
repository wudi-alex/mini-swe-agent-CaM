"""Mixin for adding dynamic reasoning effort control to agents.
Specifically adapted for LitellmResponseAPIModel.
"""

import time


class ExperimentMixin:
    """Mixin that adds dynamic reasoning effort control capability."""

    def __init__(self, *args,
                 reasoning_strategy: str = None,
                 high_reasoning_first_round: int = 3,
                 routine_high_reasoning_interval: int = 5,
                 **kwargs):
        """
        Initialize the reasoning strategy mixin.

        Args:
            reasoning_strategy: Strategy type - "first_high_reasoning", "routine_high_reasoning",
                              "ask_for_high_reasoning", or None to disable
            high_reasoning_first_round: Number of first rounds to use high reasoning
                                      (for first_high_reasoning strategy)
            routine_high_reasoning_interval: Interval for routine high reasoning
                                           (for routine_high_reasoning strategy)
        """
        self.reasoning_strategy = reasoning_strategy
        self.high_reasoning_first_round = high_reasoning_first_round
        self.routine_high_reasoning_interval = routine_high_reasoning_interval
        self.next_call_use_high = False  # Flag for ask_for_high_reasoning strategy
        self.routine_reflection_count = 0  # Counter for routine reflections
        self._reasoning_initialized = False  # Track if we've initialized reasoning support

        print(f"[ExperimentMixin] Initialized with strategy: {reasoning_strategy}")
        if reasoning_strategy == "first_high_reasoning":
            print(f"[ExperimentMixin] Will use high reasoning for first {high_reasoning_first_round} rounds")
        elif reasoning_strategy == "routine_high_reasoning":
            print(f"[ExperimentMixin] Will use high reasoning every {routine_high_reasoning_interval} rounds")
        elif reasoning_strategy == "ask_for_high_reasoning":
            print(f"[ExperimentMixin] Will use high reasoning when explicitly requested by agent")

        # Call parent initialization (supports multiple inheritance)
        super().__init__(*args, **kwargs)

    def _initialize_reasoning_support(self):
        """
        Initialize reasoning support for LitellmResponseAPIModel.
        Creates model_kwargs attribute and patches query method.
        """
        if self._reasoning_initialized or not hasattr(self, 'model'):
            return

        print(f"[ExperimentMixin] Initializing reasoning support for {type(self.model).__name__}")

        # Step 1: Create model_kwargs attribute if it doesn't exist
        if not hasattr(self.model, 'model_kwargs'):
            self.model.model_kwargs = {'reasoning': {'effort': 'low'}}
            print(f"[ExperimentMixin] Created model.model_kwargs attribute")
        else:
            print(f"[ExperimentMixin] model.model_kwargs already exists")
            # Ensure reasoning key exists
            if 'reasoning' not in self.model.model_kwargs:
                self.model.model_kwargs['reasoning'] = {'effort': 'low'}

        # Step 2: Patch the query method to inject reasoning config
        if not hasattr(self.model, '_original_query'):
            self.model._original_query = self.model.query

            def query_with_reasoning(messages, **kwargs):
                """
                Patched query method that injects reasoning configuration.
                """
                # Get current reasoning config from model_kwargs
                if hasattr(self.model, 'model_kwargs') and 'reasoning' in self.model.model_kwargs:
                    reasoning_config = self.model.model_kwargs['reasoning']

                    # Inject into kwargs
                    if 'reasoning' not in kwargs:
                        kwargs['reasoning'] = {}
                    kwargs['reasoning'].update(reasoning_config)

                    effort = reasoning_config.get('effort', 'unknown')
                    print(f"[ExperimentMixin] Injecting reasoning effort: {effort}")

                # Call original query method
                return self.model._original_query(messages, **kwargs)

            # Replace the query method
            self.model.query = query_with_reasoning
            print(f"[ExperimentMixin] Successfully patched query method")

        self._reasoning_initialized = True
        print(f"[ExperimentMixin] Reasoning support initialized successfully")

    def set_reasoning_effort(self, effort: str):
        """
        Set the reasoning effort level for the model.

        Args:
            effort: "low", "medium", or "high"
        """
        if not hasattr(self, 'model'):
            print(f"[ExperimentMixin] Warning: Model not initialized yet")
            return

        # Ensure initialization is done
        self._initialize_reasoning_support()

        # Now we can safely set the reasoning effort
        if hasattr(self.model, 'model_kwargs'):
            old_effort = self.model.model_kwargs.get('reasoning', {}).get('effort', 'unknown')
            self.model.model_kwargs['reasoning']['effort'] = effort
            print(f"[ExperimentMixin] Reasoning effort: {old_effort} -> {effort}")
        else:
            print(f"[ExperimentMixin] ERROR: model_kwargs still not available after initialization")

    def get_current_reasoning_effort(self) -> str:
        """Get the current reasoning effort level."""
        if not hasattr(self, 'model'):
            return "unknown"

        if hasattr(self.model, 'model_kwargs'):
            return self.model.model_kwargs.get('reasoning', {}).get('effort', 'unknown')

        return "unknown"

    def should_use_high_reasoning_first_round(self) -> bool:
        """
        Check if high reasoning should be used based on first_high_reasoning strategy.

        Returns:
            True if current call is within the first N rounds
        """
        if self.reasoning_strategy != "first_high_reasoning":
            return False

        # Check if we're still in the first N rounds
        current_calls = getattr(self.model, 'n_calls', 0)
        return current_calls < self.high_reasoning_first_round

    def should_use_high_reasoning_routine(self) -> bool:
        """
        Check if high reasoning should be used based on routine_high_reasoning strategy.

        Returns:
            True if we've reached the interval for routine high reasoning
        """
        if self.reasoning_strategy != "routine_high_reasoning":
            return False

        current_calls = getattr(self.model, 'n_calls', 0)

        # Check if we're at the interval point (but not at call 0)
        if current_calls > 0 and current_calls % self.routine_high_reasoning_interval == 0:
            return True

        return False

    def check_high_reasoning_request(self, output: dict) -> bool:
        """
        Check if output contains a request for high reasoning.

        Args:
            output: Command execution output

        Returns:
            True if agent requested high reasoning
        """
        if self.reasoning_strategy != "ask_for_high_reasoning":
            return False

        output_text = output.get("output", "")
        lines = output_text.lstrip().splitlines()

        # Check if first line is the high reasoning request
        if lines and lines[0].strip() == "ASK_FOR_HIGH_REASONING":
            print(f"[ExperimentMixin] Agent requested high reasoning")
            return True

        return False

    def prepare_for_next_call(self):
        """Prepare reasoning effort for the next model call based on active strategy."""

        # Strategy 1: first_high_reasoning
        if self.reasoning_strategy == "first_high_reasoning":
            if self.should_use_high_reasoning_first_round():
                self.set_reasoning_effort("high")
                current_calls = getattr(self.model, 'n_calls', 0)
                print(f"[ExperimentMixin] Using high reasoning (round {current_calls + 1}/{self.high_reasoning_first_round})")
            else:
                current_effort = self.get_current_reasoning_effort()
                if current_effort != "low":
                    self.set_reasoning_effort("low")
                    print(f"[ExperimentMixin] Switched to low reasoning after first {self.high_reasoning_first_round} rounds")

        # Strategy 3: ask_for_high_reasoning (check flag set by execute_action)
        elif self.reasoning_strategy == "ask_for_high_reasoning":
            if self.next_call_use_high:
                self.set_reasoning_effort("high")
                print(f"[ExperimentMixin] Using high reasoning for this call (agent requested)")
                self.next_call_use_high = False  # Reset flag
            else:
                current_effort = self.get_current_reasoning_effort()
                if current_effort != "low":
                    self.set_reasoning_effort("low")

    def inject_routine_reflection(self):
        """Inject a reflection prompt for routine high reasoning strategy."""
        self.routine_reflection_count += 1

        reflection_prompt = f"""
<routine_reflection checkpoint="{self.routine_reflection_count}" step="{self.model.n_calls}">
This is a routine checkpoint (every {self.routine_high_reasoning_interval} steps). Please take a moment to:

1. **Review your progress**: What have you accomplished so far?
2. **Identify issues**: Are there any mistakes or problems in your approach?
3. **Verify correctness**: Have you tested your changes? Are they working as expected?
4. **Plan next steps**: What should you do next to complete the task?
5. **Course correction**: If you're stuck or going in the wrong direction, what should you change?

Think deeply about your trajectory and make any necessary corrections before proceeding.
</routine_reflection>
"""

        print("="*80)
        print(f"[ExperimentMixin] Routine Reflection #{self.routine_reflection_count}")
        print(f"[ExperimentMixin] Step: {self.model.n_calls}")
        print("="*80)

        # Add reflection message to conversation
        self.add_message("user", reflection_prompt)

        # Set high reasoning for the next call
        self.set_reasoning_effort("high")
        print(f"[ExperimentMixin] High reasoning enabled for reflection response")

    def get_high_reasoning_instruction(self) -> str:
        """
        Get instruction text for requesting high reasoning (for ask_for_high_reasoning strategy).

        Returns:
            Instruction text to append to system prompt or task description
        """
        if self.reasoning_strategy != "ask_for_high_reasoning":
            return ""

        instruction = """

## High Reasoning Request
When you encounter a particularly challenging problem that requires deep analysis, careful planning, or complex reasoning, you can request enhanced reasoning capabilities. To do this, use the following bash command:

```bash
echo "ASK_FOR_HIGH_REASONING"
```

After executing this command, your next response will be generated with high reasoning effort, allowing for more thorough analysis and better problem-solving. Use this judiciously when you:
- Need to analyze complex code interactions
- Are stuck and need to reconsider your approach
- Need to plan a multi-step solution carefully
- Are about to make critical changes that require careful thought

Remember: High reasoning consumes more resources, so only request it when truly necessary."""

        return instruction

    def execute_action(self, action: dict) -> dict:
        """Override execute_action to handle ask_for_high_reasoning strategy."""

        # Call parent's execute_action
        output = super().execute_action(action)

        # Strategy 3: Check if agent requested high reasoning
        if self.check_high_reasoning_request(output):
            print("="*80)
            print("[ExperimentMixin] High Reasoning Request Detected")
            print("="*80)

            # Set flag to use high reasoning for the next call
            self.next_call_use_high = True

            # Add acknowledgment message
            acknowledgment = """
<high_reasoning_acknowledgment>
Your request for high reasoning has been received. The next model call will use high reasoning effort to provide more thorough analysis.
</high_reasoning_acknowledgment>
"""
            self.add_message("user", acknowledgment)
            print("[ExperimentMixin] High reasoning will be used for the next call")
            print("="*80)

        return output

    def step(self) -> dict:
        """Override step to handle strategy logic before each step."""

        # Strategy 2: routine_high_reasoning - check if we should inject reflection
        if self.should_use_high_reasoning_routine():
            self.inject_routine_reflection()
            # Note: After reflection message is added, parent's step() will be called
            # which will trigger a model call with high reasoning

        # Prepare reasoning effort for the next call (for strategies 1 and 3)
        self.prepare_for_next_call()

        # Call parent's step
        result = super().step()

        # After the step, if we used high reasoning for routine strategy, reset to low
        if self.reasoning_strategy == "routine_high_reasoning":
            current_calls = getattr(self.model, 'n_calls', 0)
            # Check if we just completed a routine high reasoning call
            if (current_calls - 1) > 0 and (current_calls - 1) % self.routine_high_reasoning_interval == 0:
                self.set_reasoning_effort("low")
                print(f"[ExperimentMixin] Reset to low reasoning after routine reflection")

        return result

    def run(self, task: str, **kwargs) -> tuple[str, str]:
        """Override run to initialize reasoning strategy at the start."""

        print("="*80)
        print("[ExperimentMixin] Starting run with ExperimentMixin")
        print(f"[ExperimentMixin] Active strategy: {self.reasoning_strategy}")
        print("="*80)

        # Initialize reasoning support (creates model_kwargs and patches query)
        if hasattr(self, 'model'):
            self._initialize_reasoning_support()
            print(f"[ExperimentMixin] Model type: {type(self.model).__name__}")
            print(f"[ExperimentMixin] Initial reasoning effort: {self.get_current_reasoning_effort()}")

        # Initialize reasoning effort based on strategy
        if self.reasoning_strategy == "first_high_reasoning":
            # Start with high reasoning
            self.set_reasoning_effort("high")
            print(f"[ExperimentMixin] Starting with high reasoning for first {self.high_reasoning_first_round} rounds")
        elif self.reasoning_strategy in ["routine_high_reasoning", "ask_for_high_reasoning"]:
            # Start with low reasoning (will be changed as needed)
            self.set_reasoning_effort("low")
            print(f"[ExperimentMixin] Starting with low reasoning")

        # For ask_for_high_reasoning strategy, append instruction to task
        if self.reasoning_strategy == "ask_for_high_reasoning":
            high_reasoning_instruction = self.get_high_reasoning_instruction()
            if high_reasoning_instruction:
                task = task + high_reasoning_instruction
                print(f"[ExperimentMixin] Appended high reasoning instruction to task")

        print("="*80)

        # Call parent's run method
        return super().run(task, **kwargs)