package com.aslannt.celeste.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val CelesteDarkColors = darkColorScheme(
    primary = Color(0xFF79D6F9),
    onPrimary = Color(0xFF002432),
    primaryContainer = Color(0xFF123A4B),
    onPrimaryContainer = Color(0xFFC4F0FF),
    secondary = Color(0xFFB7A6FF),
    onSecondary = Color(0xFF241B55),
    secondaryContainer = Color(0xFF302A5C),
    onSecondaryContainer = Color(0xFFE4DEFF),
    tertiary = Color(0xFF69E3CA),
    onTertiary = Color(0xFF00382F),
    background = Color(0xFF07111E),
    onBackground = Color(0xFFE8F2FC),
    surface = Color(0xFF0E1A28),
    onSurface = Color(0xFFE8F2FC),
    surfaceVariant = Color(0xFF172638),
    onSurfaceVariant = Color(0xFFB7C7D8),
    outline = Color(0xFF40556C),
    outlineVariant = Color(0xFF23364B),
    error = Color(0xFFFFB4AB),
    onError = Color(0xFF690005),
)

private val CelesteLightColors = lightColorScheme(
    primary = Color(0xFF076A8A),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFC3EDFF),
    onPrimaryContainer = Color(0xFF001F2A),
    secondary = Color(0xFF5D50A6),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFE5DEFF),
    onSecondaryContainer = Color(0xFF191347),
    tertiary = Color(0xFF006B5B),
    onTertiary = Color.White,
    background = Color(0xFFF4F8FC),
    onBackground = Color(0xFF101820),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF101820),
    surfaceVariant = Color(0xFFEAF0F6),
    onSurfaceVariant = Color(0xFF425466),
    outline = Color(0xFF718293),
    outlineVariant = Color(0xFFD4DEE8),
)

private val CelesteTypography = Typography(
    displaySmall = TextStyle(
        fontWeight = FontWeight.Bold,
        fontSize = 34.sp,
        lineHeight = 40.sp,
        letterSpacing = (-0.6).sp,
    ),
    headlineSmall = TextStyle(
        fontWeight = FontWeight.Bold,
        fontSize = 24.sp,
        lineHeight = 30.sp,
        letterSpacing = (-0.3).sp,
    ),
    titleLarge = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 20.sp,
        lineHeight = 26.sp,
    ),
    titleMedium = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 16.sp,
        lineHeight = 22.sp,
    ),
    bodyLarge = TextStyle(
        fontWeight = FontWeight.Normal,
        fontSize = 16.sp,
        lineHeight = 24.sp,
    ),
    bodyMedium = TextStyle(
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        lineHeight = 21.sp,
    ),
    labelLarge = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 14.sp,
        lineHeight = 18.sp,
    ),
    labelMedium = TextStyle(
        fontWeight = FontWeight.Medium,
        fontSize = 12.sp,
        lineHeight = 16.sp,
        letterSpacing = 0.2.sp,
    ),
)

private val CelesteShapes = Shapes(
    small = RoundedCornerShape(14.dp),
    medium = RoundedCornerShape(20.dp),
    large = RoundedCornerShape(28.dp),
)

@Composable
fun CelesteTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) CelesteDarkColors else CelesteLightColors,
        typography = CelesteTypography,
        shapes = CelesteShapes,
        content = content,
    )
}
