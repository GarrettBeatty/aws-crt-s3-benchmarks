namespace S3BenchRunner;

public static class Logger
{
    public static bool IsVerbose { get; private set; }

    public static void Initialize(bool isVerbose = false)
    {
        IsVerbose = isVerbose || !string.IsNullOrEmpty(Environment.GetEnvironmentVariable("S3_BENCHMARK_VERBOSE"));
    }

    public static void LogVerbose(string message)
    {
        if (IsVerbose)
        {
            Console.WriteLine(message);
        }
    }

    public static void LogAlways(string message)
    {
        Console.WriteLine(message);
    }
}
