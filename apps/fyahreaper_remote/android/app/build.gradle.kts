plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}
// CI: stable signing key from repo secrets so every build updates in place; version from the run number.
val fyahKeystore: String? = System.getenv("FYAH_KEYSTORE_FILE")
val fyahRun: Int = System.getenv("GITHUB_RUN_NUMBER")?.toIntOrNull() ?: 0
val fyahOffset: Int = System.getenv("FYAH_VERSION_OFFSET")?.toIntOrNull() ?: 0
android {
    namespace = "com.hazewave.fyahremote"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.hazewave.fyahremote"
        minSdk = 26
        targetSdk = 35
        versionCode = 1000 + fyahRun * 10 + fyahOffset
        versionName = "0.2.$fyahRun" + (if (fyahOffset != 0) ".$fyahOffset" else "")
    }
    signingConfigs {
        if (fyahKeystore != null) create("stable") {
            storeFile = file(fyahKeystore)
            storePassword = System.getenv("FYAH_KEYSTORE_PASSWORD")
            keyAlias = "fyahdebug"
            keyPassword = System.getenv("FYAH_KEYSTORE_PASSWORD")
            storeType = "pkcs12"
        }
    }
    buildTypes {
        getByName("debug") { if (fyahKeystore != null) signingConfig = signingConfigs.getByName("stable") }
    }
    buildFeatures { compose = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}
dependencies {
    implementation(platform("androidx.compose:compose-bom:2025.05.01"))
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
}
