# Optional RStudio exploration of the supplied synthetic dataset.
d <- read.csv("data/sample.csv", stringsAsFactors=FALSE)
d$day <- as.Date(d$day)
monthly <- aggregate(temperature ~ station + format(day, "%Y-%m"), d, mean)
print(monthly)
write.csv(monthly, "data/monthly_R.csv", row.names=FALSE)
plot(d$day[d$station=="Karachi"], d$temperature[d$station=="Karachi"], type="l", xlab="Date", ylab="Temperature (C)", main="EarthScape synthetic Karachi observations")
