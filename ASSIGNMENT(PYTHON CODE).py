import math


def euler_method(f, x0, y0, step_size, num_steps):
    """
    Solve a first-order ordinary differential equation using Euler's method.

    Parameters:
    f : function
        The derivative function dy/dx = f(x, y)
    x0 : float
        Initial x-value
    y0 : float
        Initial y-value at x0
    step_size : float
        Step size (h) for the approximation
    num_steps : int
        Number of steps to compute

    Returns:
    x_values, y_values : tuple of lists
        The computed x and y values
    """
    x_values = [x0]
    y_values = [y0]

    x = x0
    y = y0

    for _ in range(num_steps):
        slope = f(x, y)
        y = y + step_size * slope
        x = x + step_size

        x_values.append(x)
        y_values.append(y)

    return x_values, y_values


def main():
    """Main function to run the Euler method calculator."""
    print("Euler Method ODE Solver \n")

    # Get the differential equation from user
    print("Enter the differential equation dy/dx = f(x, y)")
    print("Examples:")
    print("  • x + y")
    print("  • x**2 - y")
    print("  • math.exp(x) - y")
    print("  • math.sin(x) + math.cos(y)")
    print("  • x*y + math.sqrt(1 + x**2)")
    print()

    # getting function input
    func_input = input("Enter f(x, y): ")

    
    try:
        
        f = lambda x, y: eval(func_input, {"math": math, "x": x, "y": y})

        # Get initial conditions and parameters
        print("\nEnter initial conditions and parameters:")
        x0 = float(input("Initial x (x0): "))
        y0 = float(input("Initial y (y0): "))
        h = float(input("Step size (h): "))
        n = int(input("Number of steps: "))

        # Solve using Euler's method
        x_points, y_points = euler_method(f, x0, y0, h, n)

        # Display results
        print("\n" + "=" * 50)
        print("Euler Method Results")
        print("=" * 50)
        print(f"ODE: dy/dx = {func_input}")
        print(f"Initial condition: y({x0}) = {y0}")
        print(f"Step size: h = {h}")
        print(f"Number of steps: {n}")
        print("-" * 50)

        # Print table of results
        print(f"{'Step':<6} {'x':<12} {'y (approx)':<15}")
        print("-" * 35)

        for i in range(len(x_points)):
            print(f"{i:<6} {x_points[i]:<12.6f} {y_points[i]:<15.8f}")

        # Final result
        print("-" * 50)
        print(f"Final approximation: y({x_points[-1]:.6f}) ≈ {y_points[-1]:.10f}")

    except Exception as e:
        print(f"\nError: {e}")
        print("Please check your function syntax and try again.")


if __name__ == "__main__":
    main()