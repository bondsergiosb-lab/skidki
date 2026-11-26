package ua.skidki.app;

import android.app.job.JobParameters;
import android.app.job.JobService;
import android.util.Log;

/** Фоновая задача: скачать скидки и показать уведомление. JobScheduler запускает её, когда есть интернет. */
public class DealsJob extends JobService {

    @Override
    public boolean onStartJob(JobParameters params) {
        boolean now = params.getJobId() == Notifier.JOB_NOW;
        new Thread(() -> {
            boolean retry = false;
            try {
                Notifier.work(getApplicationContext(), now);
            } catch (Exception e) {
                Log.w(Notifier.TAG, "не удалось подготовить уведомление", e);
                retry = !now;  // сеть пропала посреди загрузки — система повторит позже
            }
            jobFinished(params, retry);
        }).start();
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        return true;
    }
}
