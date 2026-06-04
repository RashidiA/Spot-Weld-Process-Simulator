public class WeldEngine {
    public static void main(String[] args) {
        if (args.length < 12) {
            System.out.println("ERROR: Missing arguments");
            return;
        }

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
        int targetTime = (int) Double.parseDouble(args[10]);
        double force = Double.parseDouble(args[11]);

        double totalT = t1 + t2;
        double tMin = Math.min(t1, t2);
        double avgRes = ((t1 * resFactor1) + (t2 * resFactor2)) / totalT;
        double avgKMod = ((t1 * kMod1) + (t2 * kMod2)) / totalT;

        double kFinal = kBase * avgKMod * avgRes;
        if (isZinc) kFinal *= 0.82;

        double targetMin = 4.0 * Math.sqrt(tMin);
        double tipEff = Math.pow(6.0 / dTip, 2.0);
        double expulsionLimit = (5.5 * Math.sqrt(tMin)) * Math.pow(force / 300.0, 0.1) * Math.pow(dTip / 6.0, 0.2);

        StringBuilder output = new StringBuilder();
        for (int stepTime = 1; stepTime <= targetTime; stepTime++) {
            double nuggetDiameter = kFinal * Math.pow((current * tipEff) / 10000.0, 2.0) * (stepTime / 10.0) * Math.pow(300.0 / force, 0.25) * 5.5;
            
            output.append(String.format("%d,%.4f,%.4f,%.4f", stepTime, nuggetDiameter, targetMin, expulsionLimit));
            if (stepTime < targetTime) {
                output.append("|");
            }
        }
        System.out.print(output.toString());
    }
}
