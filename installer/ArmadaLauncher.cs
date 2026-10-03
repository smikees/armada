// Windowless, branded host for the private CPython runtime shipped with ARMADA.
// It lives beside python312.dll and forwards CLI arguments to CPython in this
// process, so the native window and Task Manager both belong to ARMADA.exe.
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Reflection;

[assembly: AssemblyTitle("ARMADA")]
[assembly: AssemblyDescription("ARMADA agent management")]
[assembly: AssemblyProduct("ARMADA")]
[assembly: AssemblyCompany("Mihai Stanculescu")]

internal static class ArmadaLauncher
{
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool SetDllDirectory(string path);

    [DllImport("python312.dll", CallingConvention = CallingConvention.Cdecl)]
    private static extern int Py_Main(int argc, IntPtr argv);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int MessageBox(IntPtr owner, string message, string caption, uint type);

    [STAThread]
    private static int Main(string[] args)
    {
        string runtime = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        if (!SetDllDirectory(runtime))
        {
            MessageBox(IntPtr.Zero, "ARMADA could not locate its Python runtime.", "ARMADA — cannot start", 0x10);
            return 1;
        }

        string[] argv = Environment.GetCommandLineArgs();
        IntPtr values = IntPtr.Zero;
        IntPtr[] strings = new IntPtr[argv.Length];
        try
        {
            values = Marshal.AllocHGlobal((argv.Length + 1) * IntPtr.Size);
            for (int i = 0; i < argv.Length; i++)
            {
                strings[i] = Marshal.StringToHGlobalUni(argv[i]);
                Marshal.WriteIntPtr(values, i * IntPtr.Size, strings[i]);
            }
            Marshal.WriteIntPtr(values, argv.Length * IntPtr.Size, IntPtr.Zero);
            return Py_Main(argv.Length, values);
        }
        catch (Exception error)
        {
            MessageBox(IntPtr.Zero, "ARMADA could not start its runtime.\n\n" + error.Message,
                       "ARMADA — cannot start", 0x10);
            return 1;
        }
        finally
        {
            foreach (IntPtr value in strings)
                if (value != IntPtr.Zero) Marshal.FreeHGlobal(value);
            if (values != IntPtr.Zero) Marshal.FreeHGlobal(values);
        }
    }

}
