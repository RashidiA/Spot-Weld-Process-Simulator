public class WeldEngine {
    public static void main(String[] args) {
        if (args.length < 12) {
            System.out.println("ERROR: Missing arguments");
            return;
        }

        // Parse inputs sent from the Streamlit UI
        double t1 = Double.parseDouble(args[0]);
        double resFactor1 = Double.parseDouble(args[1]);
        double kMod1 = Double.parseDouble(args[2]);
        
        double t2 = Double.parseDouble(args[3]);
        double resFactor2 = Double.parseDouble(args[4]);
        double kMod2 = Double.parseDouble(args[5]);
        
        boolean isZinc = Boolean.parseBoolean(args[6]);
        double dTip = Double.parseDouble(args[7]);
        double kBase = Double.parseDouble(args[8]);
        double current = Double.parseDouble(args[9]);
        double time = Double.parseDouble(args[10]);
        double force = Double.parseDouble(args[11]);

        // Core Asari-Rashidi 3-Ply Formulations
        double totalT = t1 + t2;
        double tMin = Math.min(t1, t2);
        double avgRes = ((t1 * resFactor1) + (t2 * resFactor2)) / totalT;
        double avgKMod = ((t1 * kMod1) + (t2 * kMod2)) / totalT;

        double kFinal = kBase * avgKMod * avgRes;
        if (isZinc) kFinal *= 0.82;

        double targetMin = 4.0 * Math.sqrt(tMin);
        double tipEff = Math.pow(6.0 / dTip, 2.0);

        // Compute Nugget Growth and Expulsion Thresholds
        double nuggetDiameter = kFinal * Math.pow((current * tipEff) / 10000.0, 2.0) * (time / 10.0) * Math.pow(300.0 / force, 0.25) * 5.5;
        double expulsionLimit = (5.5 * Math.sqrt(tMin)) * Math.pow(force / 300.0, 0.1) * Math.pow(dTip / 6.0, 0.2) * (1.4 / 1.4);

        // Pipe formatted results back to Python terminal stream
        System.out.printf("%.4f|%.4f|%.4f", nuggetDiameter, targetMin, expulsionLimit);
    }
}